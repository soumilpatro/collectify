"""Persistent entities from Experiment 6, with cart, messaging and moderation."""
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160), unique=True)
    phone: Mapped[str] = mapped_column(String(40), default='')
    address: Mapped[str] = mapped_column(Text, default='')
    password: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(20))
    active: Mapped[int] = mapped_column(Integer, default=1)
    verification: Mapped[str] = mapped_column(String(20), default='pending')
    evidence: Mapped[str] = mapped_column(Text, default='')
    created: Mapped[str] = mapped_column(String(40), default=now)

class Category(Base):
    __tablename__ = 'categories'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)

class Product(Base):
    __tablename__ = 'products'
    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    category_id: Mapped[int] = mapped_column(ForeignKey('categories.id'))
    name: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text)
    price: Mapped[int] = mapped_column(Integer) # integer paise, never floating-point money
    condition: Mapped[str] = mapped_column(String(40))
    year: Mapped[int] = mapped_column(Integer)
    stock: Mapped[int] = mapped_column(Integer, default=1)
    image: Mapped[str] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(20), default='pending')
    authenticity: Mapped[str] = mapped_column(String(20), default='unverified')
    created: Mapped[str] = mapped_column(String(40), default=now)

class Wishlist(Base):
    __tablename__ = 'wishlists'
    __table_args__ = (UniqueConstraint('buyer_id', 'product_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id'))
    created: Mapped[str] = mapped_column(String(40), default=now)

class Cart(Base):
    __tablename__ = 'carts'
    __table_args__ = (UniqueConstraint('buyer_id', 'product_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id'))
    quantity: Mapped[int] = mapped_column(Integer, default=1)

class Order(Base):
    __tablename__ = 'orders'
    id: Mapped[int] = mapped_column(primary_key=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    seller_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id'))
    quantity: Mapped[int] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(40), default='Order Placed')
    address: Mapped[str] = mapped_column(Text)
    tracking: Mapped[str] = mapped_column(String(120), default='')
    created: Mapped[str] = mapped_column(String(40), default=now)

class Payment(Base):
    __tablename__ = 'payments'
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.id'), unique=True)
    amount: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(40))
    method: Mapped[str] = mapped_column(String(40), default='Demo gateway')
    reference: Mapped[str] = mapped_column(String(100))
    created: Mapped[str] = mapped_column(String(40), default=now)

class OrderEvent(Base):
    __tablename__ = 'order_events'
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.id'))
    state: Mapped[str] = mapped_column(String(40))
    created: Mapped[str] = mapped_column(String(40), default=now)

class Review(Base):
    __tablename__ = 'reviews'
    __table_args__ = (UniqueConstraint('buyer_id', 'product_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id'))
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text)
    created: Mapped[str] = mapped_column(String(40), default=now)

class AuthenticityVerification(Base):
    __tablename__ = 'verifications'
    id: Mapped[int] = mapped_column(primary_key=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id'))
    status: Mapped[str] = mapped_column(String(30), default='pending')
    result: Mapped[str] = mapped_column(Text, default='')
    created: Mapped[str] = mapped_column(String(40), default=now)

class Message(Base):
    __tablename__ = 'messages'
    id: Mapped[int] = mapped_column(primary_key=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    recipient_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id'))
    body: Mapped[str] = mapped_column(Text)
    created: Mapped[str] = mapped_column(String(40), default=now)

class Notification(Base):
    __tablename__ = 'notifications'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    body: Mapped[str] = mapped_column(Text)
    read: Mapped[int] = mapped_column(Integer, default=0)
    created: Mapped[str] = mapped_column(String(40), default=now)

class Dispute(Base):
    __tablename__ = 'disputes'
    id: Mapped[int] = mapped_column(primary_key=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.id'))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default='open')
    resolution: Mapped[str] = mapped_column(Text, default='')
    created: Mapped[str] = mapped_column(String(40), default=now)

class ResetToken(Base):
    __tablename__ = 'reset_tokens'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    digest: Mapped[str] = mapped_column(String(64), unique=True)
    expires: Mapped[int] = mapped_column(Integer)
    used: Mapped[int] = mapped_column(Integer, default=0)
