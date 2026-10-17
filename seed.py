"""Optional, explicitly fictional demo accounts and catalog."""
from sqlalchemy import select
from werkzeug.security import generate_password_hash
from models import User, Product, Category, Notification

def seed(db):
    if db.scalar(select(User.id).limit(1)):
        return
    accounts=[('Aarav Mehta','buyer@collectify.demo','buyer'),
              ('The Curio Cabinet','seller@collectify.demo','seller'),
              ('Collectify Admin','admin@collectify.demo','admin')]
    users=[]
    for name,email,role in accounts:
        u=User(name=name,email=email,role=role,password=generate_password_hash('Collectify123!'),
               verification='verified' if role=='seller' else 'pending',
               evidence='Demo seller: vintage camera and memorabilia collection.',
               address='42 College Road, Mumbai, Maharashtra 400001')
        db.add(u);db.flush();users.append(u)
        db.add(Notification(user_id=u.id,body='Welcome to the Collectify college demo. All catalog items and payment results are sample data.'))
    cats=[]
    for name in ['Cameras','Vinyl & Music','Watches','Coins & Stamps','Art & Objects','Books & Comics']:
        c=Category(name=name);db.add(c);db.flush();cats.append(c)
    products=[
        ('Canon AE-1 film camera',0,14500,'Excellent',1976,'camera','A classic 35mm film camera with a 50mm lens. Clean viewfinder, working shutter and a beautifully worn original strap.'),
        ('Kind of Blue · first edition',1,6800,'Good',1959,'vinyl','A sample vintage jazz pressing with its original sleeve. Light surface wear; sleeve and record condition are graded separately on request.'),
        ('Seiko 5 automatic watch',2,9200,'Excellent',1982,'watch','A stainless steel automatic watch with a warm cream dial. A timeless everyday piece with a serviced movement.'),
        ('Indian commemorative stamps',3,2400,'Mint',1969,'stamp','A curated set of commemorative stamps from a private collection. Presented in a protective archival sleeve.'),
        ('Brass nautical compass',4,4500,'Good',1965,'compass','A handsome brass pocket compass with an aged patina. A decorative collectible with an engraved case.'),
        ('The Amazing Spider-Man #129',5,18500,'Fair',1974,'comic','Sample comic listing with visible edge wear and a complete interior. Request detailed condition photos before collecting.'),
        ('Olympus Trip 35',0,7800,'Good',1972,'camera','A compact 35mm camera with a silver body and black leatherette. Sample listing, includes a protective carrying case.'),
        ('Blue Note jazz collection',1,5200,'Excellent',1963,'vinyl','A sample selection of jazz records in original sleeves. A thoughtful starting point for a vintage vinyl collection.')]
    for i,(name,cat,price,condition,year,art,description) in enumerate(products):
        db.add(Product(seller_id=users[1].id,category_id=cats[cat].id,name=name,price=price*100,
            condition=condition,year=year,image=f'/static/art/{art}.svg',description=description,
            stock=2 if i%2 else 1,status='approved',authenticity='verified' if i in [0,2,3] else 'unverified'))
    db.commit()
