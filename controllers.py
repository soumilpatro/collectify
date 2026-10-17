"""Controllers corresponding to the seven DFD processes and the UML controls."""
import base64, hashlib, io, secrets, time, csv
from pathlib import Path
from decimal import Decimal, InvalidOperation
from functools import wraps
from flask import Blueprint, g, request, session, jsonify, abort, current_app, Response
from sqlalchemy import select, or_, func, update
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image, UnidentifiedImageError
from models import *

api = Blueprint('api', __name__, url_prefix='/api')
CONDITIONS = ['Mint', 'Excellent', 'Good', 'Fair']

def rows(cls, *conditions):
    return g.db.scalars(select(cls).where(*conditions).order_by(cls.id)).all()

def get(cls, id):
    return g.db.get(cls, id) or abort(404, description='Record not found.')

def data():
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        abort(400, description='Expected a JSON object.')
    return value

def text(d, key, minimum=1, maximum=2000):
    value = d.get(key, '')
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        abort(400, description=f'{key.replace("_", " ").title()} must contain {minimum}–{maximum} characters.')
    return value.strip()

def integer(d, key, minimum=0, maximum=100000):
    try:
        value = int(d[key])
        if str(value) != str(d[key]) or not minimum <= value <= maximum:
            raise ValueError()
        return value
    except (ValueError, TypeError, KeyError):
        abort(400, description=f'Invalid {key}.')

def require(*roles):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not g.user:
                abort(401, description='Please sign in to continue.')
            if roles and g.user.role not in roles:
                abort(403, description='Your account cannot perform this action.')
            return fn(*args, **kwargs)
        return wrapped
    return decorate

def notify(uid, body):
    g.db.add(Notification(user_id=uid, body=body))

def admins(body):
    for u in rows(User, User.role=='admin', User.active==1):
        notify(u.id, body)

def user_json(u):
    return dict(id=u.id,name=u.name,email=u.email,phone=u.phone,address=u.address,
                role=u.role,active=u.active,verification=u.verification,evidence=u.evidence)

def product_json(p):
    seller=get(User,p.seller_id)
    reviews=rows(Review,Review.product_id==p.id)
    return dict(id=p.id,name=p.name,description=p.description,price=p.price,
        condition=p.condition,year=p.year,stock=p.stock,image=p.image,status=p.status,
        authenticity=p.authenticity,category=get(Category,p.category_id).name,category_id=p.category_id,
        seller_id=seller.id,seller=seller.name,seller_verified=seller.verification=='verified',
        rating=round(sum(r.rating for r in reviews)/len(reviews),1) if reviews else None,
        review_count=len(reviews))

def order_json(o):
    payment=g.db.scalar(select(Payment).where(Payment.order_id==o.id))
    return dict(id=o.id,product=product_json(get(Product,o.product_id)),buyer_id=o.buyer_id,
        buyer=get(User,o.buyer_id).name,seller_id=o.seller_id,quantity=o.quantity,total=o.total,
        status=o.status,address=o.address,tracking=o.tracking,created=o.created,
        payment_status=payment.status if payment else '',payment_reference=payment.reference if payment else '',
        events=[dict(state=e.state,created=e.created) for e in rows(OrderEvent,OrderEvent.order_id==o.id)])

def state(o, name):
    o.status=name
    g.db.add(OrderEvent(order_id=o.id,state=name))

def visible(p):
    seller=get(User,p.seller_id)
    return p.status=='approved' and seller.active and seller.verification=='verified'

# 1. UserController: identity and profile
@api.get('/session')
def current_session():
    session.setdefault('csrf',secrets.token_hex(32))
    return jsonify(user=user_json(g.user) if g.user else None,csrf=session['csrf'])

@api.post('/register')
def register():
    d=data(); role=d.get('role')
    if role not in ['buyer','seller']:
        abort(400,description='Choose buyer or seller.')
    email=text(d,'email',5,160).lower()
    if '@' not in email or '.' not in email.split('@')[-1]:
        abort(400,description='Enter a valid email address.')
    if d.get('accept_policy') is not True:
        abort(400,description='Please accept the marketplace policies.')
    u=User(name=text(d,'name',2,120),email=email,role=role,
           password=generate_password_hash(text(d,'password',8,128)))
    g.db.add(u);g.db.flush();notify(u.id,'Welcome to Collectify. Your collection starts here.')
    if role=='seller': admins(f'New seller {u.name} awaits verification.')
    g.db.commit();session.clear();session.update(uid=u.id,csrf=secrets.token_hex(32))
    return jsonify(user=user_json(u),csrf=session['csrf']),201

@api.post('/login')
def login():
    d=data(); email=text(d,'email',5,160).lower()
    # Bounded per-session failed attempts; deployment should add shared rate limiting.
    attempts=session.get('attempts',[])
    attempts=[t for t in attempts if t>time.time()-300]
    if len(attempts)>=10: abort(429,description='Too many attempts. Try again in five minutes.')
    u=g.db.scalar(select(User).where(User.email==email))
    if not u or not check_password_hash(u.password,text(d,'password',1,128)) or not u.active:
        session['attempts']=attempts+[time.time()]
        abort(401,description='Email or password is incorrect, or the account is suspended.')
    session.clear();session.update(uid=u.id,csrf=secrets.token_hex(32))
    return jsonify(user=user_json(u),csrf=session['csrf'])

@api.post('/logout')
def logout():
    session.clear();session['csrf']=secrets.token_hex(32)
    return jsonify(csrf=session['csrf'])

@api.put('/profile')
@require()
def profile():
    d=data();g.user.name=text(d,'name',2,120);g.user.phone=text(d,'phone',0,40)
    g.user.address=text(d,'address',0,1000)
    if g.user.role=='seller':
        g.user.evidence=text(d,'evidence',0,2000)
        if d.get('resubmit'):
            g.user.verification='pending';admins(f'{g.user.name} submitted seller verification details.')
    g.db.commit();return jsonify(user=user_json(g.user))

@api.post('/forgot-password')
def forgot():
    d=data();u=g.db.scalar(select(User).where(User.email==text(d,'email',5,160).lower()))
    if u:
        token=secrets.token_urlsafe(32)
        g.db.add(ResetToken(user_id=u.id,digest=hashlib.sha256(token.encode()).hexdigest(),expires=int(time.time()+900)))
        g.db.commit()
        # Local delivery adapter: the token is deliberately only printed to the server console.
        print(f'LOCAL PASSWORD RECOVERY for {u.email}: {token}',flush=True)
    return jsonify(message='If the account exists, a recovery token was sent to the local server console. It expires in 15 minutes.')

@api.post('/reset-password')
def reset_password():
    d=data(); digest=hashlib.sha256(text(d,'token',20,100).encode()).hexdigest()
    token=g.db.scalar(select(ResetToken).where(ResetToken.digest==digest,ResetToken.used==0,ResetToken.expires>int(time.time())))
    if not token: abort(400,description='This recovery token is invalid or expired.')
    get(User,token.user_id).password=generate_password_hash(text(d,'password',8,128))
    for t in rows(ResetToken,ResetToken.user_id==token.user_id): t.used=1
    g.db.commit();return jsonify(message='Password changed. You can now sign in.')

# 2 and 3. ProductController: listing management, search and browse
@api.get('/categories')
def categories():
    return jsonify(categories=[dict(id=c.id,name=c.name) for c in rows(Category)],conditions=CONDITIONS)

@api.get('/products')
def products():
    q=select(Product).join(User,User.id==Product.seller_id).where(Product.status=='approved',User.active==1,User.verification=='verified')
    term=request.args.get('q','').strip()[:180]
    if term: q=q.where(or_(Product.name.ilike('%'+term+'%'),Product.description.ilike('%'+term+'%')))
    if request.args.get('category'): q=q.where(Product.category_id==request.args['category'])
    if request.args.get('condition'): q=q.where(Product.condition==request.args['condition'])
    for key,op in [('min',Product.price.__ge__),('max',Product.price.__le__)]:
        if request.args.get(key):
            try: q=q.where(op(int(Decimal(request.args[key])*100)))
            except (InvalidOperation,ValueError): abort(400,description='Invalid price filter.')
    if request.args.get('verified')=='1': q=q.where(Product.authenticity=='verified')
    sort=request.args.get('sort')
    q=q.order_by(Product.price.asc() if sort=='price-up' else Product.price.desc() if sort=='price-down' else Product.id.desc())
    return jsonify(products=[product_json(p) for p in g.db.scalars(q).all()])

@api.get('/products/<int:id>')
def detail(id):
    p=get(Product,id)
    if not visible(p) and (not g.user or (g.user.id!=p.seller_id and g.user.role!='admin')):
        abort(404,description='This listing is unavailable.')
    return jsonify(product=product_json(p),reviews=[dict(id=r.id,buyer=get(User,r.buyer_id).name,
        buyer_id=r.buyer_id,rating=r.rating,comment=r.comment,created=r.created) for r in rows(Review,Review.product_id==id)])

def product_fields(p,d):
    p.name=text(d,'name',3,180);p.description=text(d,'description',15,4000)
    try:
        money=Decimal(str(d.get('price','')))
        if not money.is_finite() or money<=0 or money>10000000 or money*100 != (money*100).to_integral_value(): raise ValueError()
        p.price=int(money*100)
    except (ValueError,InvalidOperation): abort(400,description='Enter a positive price with at most two decimal places.')
    p.condition=d.get('condition')
    if p.condition not in CONDITIONS: abort(400,description='Choose a standard condition grade.')
    p.category_id=integer(d,'category_id',1);get(Category,p.category_id)
    p.year=integer(d,'year',1500,datetime.now().year)
    p.stock=integer(d,'stock',0,1000)
    image=d.get('image','/static/art/camera.svg')
    if not isinstance(image,str) or not image.startswith(('/static/art/','/static/uploads/')) or '..' in image:
        abort(400,description='Upload a product image or select a local illustration.')
    p.image=image

@api.get('/seller/listings')
@require('seller')
def listings():
    return jsonify(products=[product_json(p) for p in rows(Product,Product.seller_id==g.user.id)])

@api.post('/products')
@require('seller')
def create_product():
    p=Product(seller_id=g.user.id);product_fields(p,data());g.db.add(p);g.db.flush()
    admins(f'Listing #{p.id}: {p.name} awaits approval.');g.db.commit()
    return jsonify(product=product_json(p)),201

@api.put('/products/<int:id>')
@require('seller')
def edit_product(id):
    p=get(Product,id)
    if p.seller_id!=g.user.id: abort(403)
    product_fields(p,data());p.status='pending';p.authenticity='unverified'
    admins(f'Updated listing #{p.id} needs review.');g.db.commit();return jsonify(product=product_json(p))

@api.delete('/products/<int:id>')
@require('seller','admin')
def remove_product(id):
    p=get(Product,id)
    if g.user.role=='seller' and p.seller_id!=g.user.id: abort(403)
    p.status='removed';notify(p.seller_id,f'{p.name} was removed from the marketplace.')
    g.db.commit();return jsonify(message='Listing removed; existing order records are preserved.')

@api.post('/uploads')
@require('seller')
def upload():
    file=request.files.get('image')
    if not file: abort(400,description='Select an image.')
    try:
        im=Image.open(file.stream)
        if im.width*im.height>20000000: raise ValueError()
        im.load();im.thumbnail((1400,1400));im=im.convert('RGB')
    except (UnidentifiedImageError,ValueError,OSError,Image.DecompressionBombError):
        abort(400,description='Upload a valid JPG, PNG or WebP image below 5 MB.')
    folder=Path(current_app.static_folder)/'uploads';folder.mkdir(exist_ok=True)
    name=secrets.token_hex(16)+'.jpg';im.save(folder/name,quality=88)
    return jsonify(image='/static/uploads/'+name)

# Wishlist and cart are server-side per buyer.
@api.get('/wishlist')
@require('buyer')
def wishlist():
    return jsonify(products=[product_json(get(Product,w.product_id)) for w in rows(Wishlist,Wishlist.buyer_id==g.user.id)])

@api.post('/wishlist/<int:id>')
@require('buyer')
def toggle_wishlist(id):
    p=get(Product,id)
    old=g.db.scalar(select(Wishlist).where(Wishlist.buyer_id==g.user.id,Wishlist.product_id==id))
    if old: g.db.delete(old)
    else:
        if not visible(p): abort(400,description='This item is unavailable.')
        g.db.add(Wishlist(buyer_id=g.user.id,product_id=id))
    g.db.commit();return jsonify(saved=not bool(old))

@api.get('/cart')
@require('buyer')
def cart():
    items=[dict(product=product_json(get(Product,c.product_id)),quantity=c.quantity) for c in rows(Cart,Cart.buyer_id==g.user.id)]
    return jsonify(items=items,total=sum(x['product']['price']*x['quantity'] for x in items))

@api.put('/cart/<int:id>')
@require('buyer')
def cart_update(id):
    p=get(Product,id);qty=integer(data(),'quantity',0,1000)
    c=g.db.scalar(select(Cart).where(Cart.buyer_id==g.user.id,Cart.product_id==id))
    if qty and (not visible(p) or qty>p.stock): abort(409,description='This quantity is unavailable.')
    if not qty:
        if c: g.db.delete(c)
    elif c: c.quantity=qty
    else: g.db.add(Cart(buyer_id=g.user.id,product_id=id,quantity=qty))
    g.db.commit();return jsonify(message='Cart updated.')

# 4. OrderController / PaymentController: guarded atomic lifecycle.
@api.post('/checkout')
@require('buyer')
def checkout():
    d=data();address=text(d,'address',10,1000);outcome=d.get('outcome')
    if outcome not in ['success','failure']: abort(400,description='Choose a demo payment outcome.')
    carts=rows(Cart,Cart.buyer_id==g.user.id)
    if not carts: abort(400,description='Your cart is empty.')
    created=[]
    # All reservations and all orders commit together or roll back together.
    for c in sorted(carts,key=lambda x:x.product_id):
        p=get(Product,c.product_id)
        if not visible(p): abort(409,description=f'{p.name} is no longer available.')
        if outcome=='success':
            changed=g.db.execute(update(Product).where(Product.id==p.id,Product.stock>=c.quantity,Product.status=='approved')
                .values(stock=Product.stock-c.quantity)).rowcount
            if changed!=1: abort(409,description=f'Not enough stock for {p.name}.')
        elif c.quantity>p.stock: abort(409,description='This quantity is unavailable.')
        o=Order(buyer_id=g.user.id,seller_id=p.seller_id,product_id=p.id,quantity=c.quantity,total=p.price*c.quantity,address=address)
        g.db.add(o);g.db.flush()
        for s in ['Order Initiated','User Authenticated','Item Selected','Order Placed','Payment Processing']:
            state(o,s)
        pay=Payment(order_id=o.id,amount=o.total,status='successful' if outcome=='success' else 'failed',reference='DEMO-'+secrets.token_hex(6).upper())
        g.db.add(pay)
        if outcome=='success':
            state(o,'Payment Successful');state(o,'Order Confirmed');g.db.delete(c)
            notify(o.buyer_id,f'Order #{o.id} confirmed. Demo payment successful.')
            notify(o.seller_id,f'New order #{o.id}: {p.name}. Please begin processing.')
        else:
            state(o,'Payment Failed');notify(o.buyer_id,f'Demo payment for order #{o.id} failed. Your cart is unchanged.')
        created.append(o)
    g.db.commit();return jsonify(orders=[order_json(o) for o in created],demo=True),201

@api.get('/orders')
@require()
def orders():
    condition=Order.buyer_id==g.user.id if g.user.role=='buyer' else Order.seller_id==g.user.id
    values=rows(Order) if g.user.role=='admin' else rows(Order,condition)
    return jsonify(orders=[order_json(o) for o in reversed(values)])

@api.post('/orders/<int:id>/cancel')
@require('buyer')
def cancel(id):
    o=get(Order,id)
    if o.buyer_id!=g.user.id: abort(403)
    if o.status not in ['Order Placed','Order Confirmed','Order Processing']:
        abort(409,description='Cancellation is available only before shipment.')
    pay=g.db.scalar(select(Payment).where(Payment.order_id==id))
    # Conditional update avoids double inventory restoration on concurrent cancellation.
    previous=o.status
    changed=g.db.execute(update(Order).where(Order.id==id,Order.status==previous).values(status='Order Cancelled')).rowcount
    if changed!=1: abort(409,description='Order changed. Please refresh.')
    if pay and pay.status=='successful':
        pay.status='refunded'
        g.db.execute(update(Product).where(Product.id==o.product_id).values(stock=Product.stock+o.quantity))
    state(o,'Order Cancelled');notify(o.seller_id,f'Order #{id} was cancelled.');notify(o.buyer_id,f'Order #{id} cancelled. Any demo payment is refunded.')
    g.db.commit();return jsonify(order=order_json(o))

@api.put('/orders/<int:id>/status')
@require('seller')
def status(id):
    o=get(Order,id);d=data()
    if o.seller_id!=g.user.id: abort(403)
    nexts={'Order Confirmed':'Order Processing','Order Processing':'Order Shipped','Order Shipped':'Order Delivered'}
    target=d.get('status')
    if target!=nexts.get(o.status): abort(409,description='This transition is not allowed by the order lifecycle.')
    if target=='Order Shipped': o.tracking=text(d,'tracking',3,120)
    changed=g.db.execute(update(Order).where(Order.id==id,Order.status==o.status).values(status=target)).rowcount
    if changed!=1: abort(409,description='Order changed. Please refresh.')
    state(o,target);notify(o.buyer_id,f'Order #{id}: {target}.');g.db.commit();return jsonify(order=order_json(o))

# 5. VerificationController: seller verification and authenticity.
@api.post('/products/<int:id>/verification')
@require('buyer')
def request_verification(id):
    p=get(Product,id)
    if not visible(p): abort(400,description='This product is unavailable.')
    if rows(AuthenticityVerification,AuthenticityVerification.buyer_id==g.user.id,AuthenticityVerification.product_id==id,AuthenticityVerification.status=='pending'):
        abort(409,description='You already have a pending request for this item.')
    v=AuthenticityVerification(buyer_id=g.user.id,product_id=id);g.db.add(v)
    admins(f'Authenticity review requested for {p.name}.');g.db.commit();return jsonify(message='Verification requested.'),201

@api.get('/verifications')
@require('buyer','admin')
def verifications():
    vs=rows(AuthenticityVerification) if g.user.role=='admin' else rows(AuthenticityVerification,AuthenticityVerification.buyer_id==g.user.id)
    return jsonify(verifications=[dict(id=v.id,product=product_json(get(Product,v.product_id)),status=v.status,result=v.result,created=v.created) for v in vs])

@api.put('/verifications/<int:id>')
@require('admin')
def verify_item(id):
    v=get(AuthenticityVerification,id);d=data()
    if v.status!='pending': abort(409,description='This request has already been reviewed.')
    if d.get('status') not in ['verified','rejected']: abort(400)
    v.status=d['status'];v.result=text(d,'result',10,2000)
    get(Product,v.product_id).authenticity=v.status
    notify(v.buyer_id,f'Authenticity request #{id}: {v.status}. {v.result}');g.db.commit();return jsonify(message='Verification result saved.')

# 6. Reviews and private buyer/seller communication.
@api.put('/products/<int:id>/review')
@require('buyer')
def review(id):
    p=get(Product,id)
    if not visible(p): abort(400,description='This listing is unavailable.')
    d=data();r=g.db.scalar(select(Review).where(Review.buyer_id==g.user.id,Review.product_id==id))
    if not r: r=Review(buyer_id=g.user.id,product_id=id);g.db.add(r)
    r.rating=integer(d,'rating',1,5);r.comment=text(d,'comment',3,1500)
    notify(p.seller_id,f'A collector reviewed {p.name}.');g.db.commit();return jsonify(message='Review saved.')

@api.delete('/products/<int:id>/review')
@require('buyer')
def delete_review(id):
    r=g.db.scalar(select(Review).where(Review.buyer_id==g.user.id,Review.product_id==id))
    if r: g.db.delete(r)
    g.db.commit();return jsonify(message='Your review was removed.')

@api.get('/messages')
@require('buyer','seller')
def messages():
    ms=rows(Message,or_(Message.sender_id==g.user.id,Message.recipient_id==g.user.id))
    return jsonify(messages=[dict(id=m.id,sender_id=m.sender_id,recipient_id=m.recipient_id,
        sender=get(User,m.sender_id).name,recipient=get(User,m.recipient_id).name,
        product_id=m.product_id,product=get(Product,m.product_id).name,body=m.body,created=m.created) for m in ms])

@api.post('/messages')
@require('buyer','seller')
def send_message():
    d=data();p=get(Product,integer(d,'product_id',1));recipient=get(User,integer(d,'recipient_id',1))
    if not recipient.active: abort(400,description='This account is unavailable.')
    if g.user.role=='buyer':
        allowed=recipient.id==p.seller_id and visible(p)
    else:
        allowed=p.seller_id==g.user.id and recipient.role=='buyer' and bool(rows(Message,Message.sender_id==recipient.id,Message.recipient_id==g.user.id,Message.product_id==p.id))
    if not allowed: abort(403,description='You may message the item seller, or reply to an existing buyer conversation.')
    g.db.add(Message(sender_id=g.user.id,recipient_id=recipient.id,product_id=p.id,body=text(d,'body',1,2000)))
    notify(recipient.id,f'New message from {g.user.name} about {p.name}.');g.db.commit();return jsonify(message='Message sent.'),201

# 7. Notifications, reports and admin moderation.
@api.get('/notifications')
@require()
def notifications():
    return jsonify(notifications=[dict(id=n.id,body=n.body,read=n.read,created=n.created) for n in reversed(rows(Notification,Notification.user_id==g.user.id))])

@api.post('/notifications/read')
@require()
def read_notifications():
    for n in rows(Notification,Notification.user_id==g.user.id): n.read=1
    g.db.commit();return jsonify(message='All notifications marked as read.')

@api.get('/admin/users')
@require('admin')
def users():
    return jsonify(users=[user_json(u) for u in rows(User)])

@api.put('/admin/users/<int:id>')
@require('admin')
def manage_user(id):
    u=get(User,id);d=data()
    if u.role=='admin': abort(400,description='Administrator accounts are protected.')
    if 'active' in d: u.active=integer(d,'active',0,1)
    if 'name' in d: u.name=text(d,'name',2,120)
    if 'verification' in d:
        if u.role!='seller' or d['verification'] not in ['verified','rejected','pending']: abort(400)
        u.verification=d['verification'];notify(id,f'Seller verification: {u.verification}.')
    g.db.commit();return jsonify(user=user_json(u))

@api.get('/admin/products')
@require('admin')
def admin_products():
    return jsonify(products=[product_json(p) for p in rows(Product)])

@api.put('/admin/products/<int:id>')
@require('admin')
def moderate(id):
    p=get(Product,id);d=data()
    if d.get('status') not in ['approved','rejected','removed']: abort(400)
    if d['status']=='approved' and get(User,p.seller_id).verification!='verified':
        abort(409,description='Verify the seller before approving their listing.')
    p.status=d['status'];notify(p.seller_id,f'Listing {p.name}: {p.status}.');g.db.commit();return jsonify(message='Moderation saved.')

@api.post('/categories')
@require('admin')
def add_category():
    c=Category(name=text(data(),'name',2,80));g.db.add(c);g.db.commit();return jsonify(id=c.id),201

@api.put('/categories/<int:id>')
@require('admin')
def rename_category(id):
    c=get(Category,id);c.name=text(data(),'name',2,80);g.db.commit();return jsonify(message='Category renamed.')

@api.delete('/categories/<int:id>')
@require('admin')
def delete_category(id):
    if rows(Product,Product.category_id==id): abort(409,description='Move products to another category before deleting this category.')
    g.db.delete(get(Category,id));g.db.commit();return jsonify(message='Category deleted.')

@api.get('/reports')
@require('admin','seller')
def reports():
    orders=rows(Order) if g.user.role=='admin' else rows(Order,Order.seller_id==g.user.id)
    good=[o for o in orders if o.status in ['Order Confirmed','Order Processing','Order Shipped','Order Delivered']]
    if request.args.get('format')=='csv':
        out=io.StringIO();writer=csv.writer(out);writer.writerow(['Order','Item','Quantity','Amount INR','Status','Created'])
        for o in orders:
            name=get(Product,o.product_id).name
            if name.startswith(('=','+','-','@')): name="'"+name
            writer.writerow([o.id,name,o.quantity,format(Decimal(o.total)/100,'.2f'),o.status,o.created])
        return Response(out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=collectify-report.csv'})
    return jsonify(order_count=len(orders),successful_orders=len(good),sales=sum(o.total for o in good),
        delivered=sum(o.status=='Order Delivered' for o in orders),
        states=[dict(status=s,count=sum(o.status==s for o in orders)) for s in sorted(set(o.status for o in orders))])

@api.post('/disputes')
@require('buyer')
def open_dispute():
    d=data();o=get(Order,integer(d,'order_id',1))
    if o.buyer_id!=g.user.id: abort(403)
    if rows(Dispute,Dispute.order_id==o.id,Dispute.status=='open'): abort(409,description='This order already has an open dispute.')
    g.db.add(Dispute(buyer_id=g.user.id,order_id=o.id,reason=text(d,'reason',10,2000)))
    admins(f'Dispute opened for order #{o.id}.');g.db.commit();return jsonify(message='Dispute sent to the administrator.'),201

@api.get('/disputes')
@require('buyer','admin')
def disputes():
    ds=rows(Dispute) if g.user.role=='admin' else rows(Dispute,Dispute.buyer_id==g.user.id)
    return jsonify(disputes=[dict(id=d.id,order_id=d.order_id,reason=d.reason,status=d.status,resolution=d.resolution) for d in ds])

@api.put('/disputes/<int:id>')
@require('admin')
def resolve_dispute(id):
    d=get(Dispute,id)
    if d.status!='open': abort(409,description='This dispute is already resolved.')
    d.resolution=text(data(),'resolution',10,2000);d.status='resolved'
    notify(d.buyer_id,f'Dispute #{id} resolved: {d.resolution}');g.db.commit();return jsonify(message='Dispute resolved.')
