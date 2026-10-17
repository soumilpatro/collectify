"""Behavioral tests: roles, privacy, moderation and order statechart guards."""
import io, unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app
from seed import seed
from models import *
from sqlalchemy import select
from PIL import Image

class CollectifyFlows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=create_app('sqlite:///:memory:',True)
        cls.db=cls.app.extensions['db_factory']

    def setUp(self):
        engine=self.app.extensions['engine']
        Base.metadata.drop_all(engine);Base.metadata.create_all(engine)
        with self.db() as db: seed(db)
        self.buyer=self.client('buyer');self.seller=self.client('seller');self.admin=self.client('admin')

    def client(self,role=None):
        c=self.app.test_client();c.csrf=c.get('/api/session').json['csrf']
        if role:
            r=self.call(c,'/login',{'email':role+'@collectify.demo','password':'Collectify123!'})
            self.assertEqual(r.status_code,200);c.csrf=r.json['csrf']
        return c

    def call(self,c,path,body=None,method='POST'):
        return c.open('/api'+path,method=method,json=body,headers={'X-CSRF-Token':c.csrf})

    def checkout(self,outcome='success'):
        self.assertEqual(self.call(self.buyer,'/cart/1',{'quantity':1},'PUT').status_code,200)
        r=self.call(self.buyer,'/checkout',{'address':'42 College Road, Mumbai 400001','outcome':outcome})
        self.assertEqual(r.status_code,201);return r.json['orders'][0]

    def test_search_filters(self):
        r=self.buyer.get('/api/products?q=Canon&condition=Excellent&max=15000&verified=1')
        self.assertEqual(len(r.json['products']),1)
        self.assertEqual(self.buyer.get('/api/products?min=20000').json['products'],[])

    def test_csrf_and_admin_role_guards(self):
        self.assertEqual(self.buyer.post('/api/checkout',json={}).status_code,403)
        self.assertEqual(self.buyer.get('/api/admin/users').status_code,403)
        self.assertEqual(self.call(self.buyer,'/admin/users/2',{'verification':'verified'},'PUT').status_code,403)
        self.assertEqual(self.call(self.seller,'/cart/1',{'quantity':1},'PUT').status_code,403)

    def test_registration_passwords_and_profile(self):
        c=self.client();r=self.call(c,'/register',{'name':'New Buyer','email':'new@example.com','password':'Password123!','role':'buyer','accept_policy':True})
        self.assertEqual(r.status_code,201);c.csrf=r.json['csrf']
        self.assertEqual(self.call(c,'/profile',{'name':'New Name','phone':'1234567890','address':'Mumbai'},'PUT').status_code,200)
        with self.db() as db:
            u=db.scalar(select(User).where(User.email=='new@example.com'))
            self.assertNotEqual(u.password,'Password123!');self.assertEqual(u.name,'New Name')
        self.assertEqual(self.call(self.client(),'/register',{'name':'Admin','email':'a@example.com','password':'Password123!','role':'admin','accept_policy':True}).status_code,400)

    def test_wishlist_cart_persistence(self):
        self.assertEqual(self.call(self.buyer,'/wishlist/1',{}).status_code,200)
        self.assertEqual(self.client('buyer').get('/api/wishlist').json['products'][0]['id'],1)
        self.call(self.buyer,'/wishlist/1',{})
        self.assertEqual(self.buyer.get('/api/wishlist').json['products'],[])
        self.assertEqual(self.call(self.buyer,'/cart/1',{'quantity':2},'PUT').status_code,409)

    def test_payment_failure_no_inventory_loss(self):
        o=self.checkout('failure');self.assertEqual(o['status'],'Payment Failed')
        self.assertEqual(self.buyer.get('/api/products/1').json['product']['stock'],1)
        self.assertEqual(len(self.buyer.get('/api/cart').json['items']),1)
        self.assertEqual(self.call(self.buyer,f'/orders/{o["id"]}/cancel',{}).status_code,409)

    def test_success_order_complete_statechart(self):
        o=self.checkout();id=o['id'];self.assertEqual(o['status'],'Order Confirmed')
        self.assertEqual([e['state'] for e in o['events']],['Order Initiated','User Authenticated','Item Selected','Order Placed','Payment Processing','Payment Successful','Order Confirmed'])
        self.assertEqual(self.buyer.get('/api/products/1').json['product']['stock'],0)
        self.assertEqual(self.buyer.get('/api/cart').json['items'],[])
        self.assertEqual(self.call(self.seller,f'/orders/{id}/status',{'status':'Order Delivered'},'PUT').status_code,409)
        for s in ['Order Processing','Order Shipped','Order Delivered']:
            r=self.call(self.seller,f'/orders/{id}/status',{'status':s,'tracking':'DEMO-TRACK-001'},'PUT');self.assertEqual(r.status_code,200)
        self.assertEqual(self.call(self.buyer,f'/orders/{id}/cancel',{}).status_code,409)
        report=self.seller.get('/api/reports').json;self.assertEqual(report['delivered'],1)

    def test_cancellation_refunds_exactly_once(self):
        o=self.checkout();id=o['id']
        self.assertEqual(self.call(self.buyer,f'/orders/{id}/cancel',{}).status_code,200)
        self.assertEqual(self.call(self.buyer,f'/orders/{id}/cancel',{}).status_code,409)
        self.assertEqual(self.buyer.get('/api/products/1').json['product']['stock'],1)
        self.assertEqual(self.buyer.get('/api/orders').json['orders'][0]['payment_status'],'refunded')
        self.assertEqual(self.seller.get('/api/reports').json['sales'],0)

    def test_cross_buyer_privacy_and_ownership(self):
        o=self.checkout();c=self.client()
        r=self.call(c,'/register',{'name':'Other Buyer','email':'other@example.com','password':'Password123!','role':'buyer','accept_policy':True});c.csrf=r.json['csrf']
        self.assertEqual(c.get('/api/orders').json['orders'],[])
        self.assertEqual(self.call(c,f'/orders/{o["id"]}/cancel',{}).status_code,403)
        self.assertEqual(self.call(c,'/disputes',{'order_id':o['id'],'reason':'Other buyer cannot own this order'}).status_code,403)
        self.call(self.buyer,'/messages',{'recipient_id':2,'product_id':1,'body':'Is the camera lens included?'})
        self.assertEqual(c.get('/api/messages').json['messages'],[])

    def test_seller_moderation_and_user_suspension(self):
        self.call(self.admin,'/admin/users/2',{'active':0},'PUT')
        self.assertEqual(self.seller.get('/api/seller/listings').status_code,401)
        self.assertEqual(self.buyer.get('/api/products').json['products'],[])
        self.call(self.admin,'/admin/users/2',{'active':1,'verification':'rejected'},'PUT')
        self.assertEqual(self.call(self.admin,'/admin/products/1',{'status':'approved'},'PUT').status_code,409)

    def test_listing_creation_edit_and_approval(self):
        payload={'name':'Vintage test camera','description':'A camera with original lens and complete condition notes.','price':'125.50','condition':'Good','year':1980,'stock':1,'image':'/static/art/camera.svg','category_id':1}
        r=self.call(self.seller,'/products',payload);self.assertEqual(r.status_code,201);id=r.json['product']['id']
        self.assertEqual(self.buyer.get('/api/products/'+str(id)).status_code,404)
        self.assertEqual(self.call(self.admin,f'/admin/products/{id}',{'status':'approved'},'PUT').status_code,200)
        self.assertEqual(self.buyer.get(f'/api/products/{id}').status_code,200)
        self.assertEqual(self.call(self.seller,f'/products/{id}',payload,'PUT').json['product']['status'],'pending')
        payload['price']='-1';self.assertEqual(self.call(self.seller,'/products',payload).status_code,400)

    def test_reviews_and_verification(self):
        self.assertEqual(self.call(self.buyer,'/products/1/review',{'rating':6,'comment':'Invalid rating'},'PUT').status_code,400)
        for rating in [5,4]: self.assertEqual(self.call(self.buyer,'/products/1/review',{'rating':rating,'comment':'A great classic camera.'},'PUT').status_code,200)
        self.assertEqual(len(self.buyer.get('/api/products/1').json['reviews']),1)
        self.assertEqual(self.call(self.buyer,'/products/1/verification',{}).status_code,201)
        self.assertEqual(self.call(self.buyer,'/products/1/verification',{}).status_code,409)
        id=self.admin.get('/api/verifications').json['verifications'][0]['id']
        self.assertEqual(self.call(self.admin,f'/verifications/{id}',{'status':'verified','result':'Provenance documentation reviewed for this demo.'},'PUT').status_code,200)
        self.assertEqual(self.buyer.get('/api/verifications').json['verifications'][0]['status'],'verified')
        self.call(self.buyer,'/products/1/review',method='DELETE');self.assertEqual(self.buyer.get('/api/products/1').json['reviews'],[])

    def test_private_message_reply_and_notifications(self):
        self.assertEqual(self.call(self.buyer,'/messages',{'recipient_id':3,'product_id':1,'body':'Cannot send item messages to admin'}).status_code,403)
        self.call(self.buyer,'/messages',{'recipient_id':2,'product_id':1,'body':'Is the original strap included?'})
        self.assertEqual(self.call(self.seller,'/messages',{'recipient_id':1,'product_id':1,'body':'Yes, the strap is included.'}).status_code,201)
        self.assertEqual(len(self.buyer.get('/api/messages').json['messages']),2)
        self.call(self.buyer,'/notifications/read',{});self.assertTrue(all(n['read'] for n in self.buyer.get('/api/notifications').json['notifications']))

    def test_disputes_categories_and_csv(self):
        o=self.checkout();self.call(self.buyer,'/disputes',{'order_id':o['id'],'reason':'Please clarify the condition of the lens.'})
        id=self.admin.get('/api/disputes').json['disputes'][0]['id']
        self.assertEqual(self.call(self.admin,f'/disputes/{id}',{'resolution':'Seller will provide additional lens photographs.'},'PUT').status_code,200)
        self.assertEqual(self.buyer.get('/api/disputes').json['disputes'][0]['status'],'resolved')
        r=self.call(self.admin,'/categories',{'name':'Trading cards'});id=r.json['id']
        self.assertEqual(self.call(self.admin,f'/categories/{id}',{'name':'Sports cards'},'PUT').status_code,200)
        self.assertEqual(self.call(self.admin,f'/categories/{id}',method='DELETE').status_code,200)
        self.assertEqual(self.call(self.admin,'/categories/1',method='DELETE').status_code,409)
        csv=self.seller.get('/api/reports?format=csv');self.assertEqual(csv.status_code,200);self.assertIn(b'Canon',csv.data)

    def test_upload_validation(self):
        im=Image.new('RGB',(40,40),'green');out=io.BytesIO();im.save(out,'PNG');out.seek(0)
        r=self.seller.post('/api/uploads',data={'image':(out,'test.png')},headers={'X-CSRF-Token':self.seller.csrf})
        self.assertEqual(r.status_code,200);self.assertTrue(r.json['image'].endswith('.jpg'))
        (Path(self.app.static_folder)/r.json['image'].split('/')[-2]/r.json['image'].split('/')[-1]).unlink()
        r=self.seller.post('/api/uploads',data={'image':(io.BytesIO(b'<script>bad</script>'),'bad.svg')},headers={'X-CSRF-Token':self.seller.csrf})
        self.assertEqual(r.status_code,400)

    def test_atomic_multi_item_checkout_rollback(self):
        self.call(self.buyer,'/cart/1',{'quantity':1},'PUT');self.call(self.buyer,'/cart/2',{'quantity':1},'PUT')
        with self.db() as db: db.get(Product,2).stock=0;db.commit()
        r=self.call(self.buyer,'/checkout',{'address':'A valid full street address in Mumbai','outcome':'success'})
        self.assertEqual(r.status_code,409)
        self.assertEqual(self.buyer.get('/api/products/1').json['product']['stock'],1)
        self.assertEqual(self.buyer.get('/api/orders').json['orders'],[])

if __name__=='__main__':unittest.main(verbosity=2)
