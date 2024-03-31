from config import app_config
from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text, ForeignKey
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from typing import List
import urllib, hashlib
from forms import *

'''
Make sure the required packages are installed: 
Open the Terminal in PyCharm (bottom left). 

On Windows type:
python -m pip install -r requirements.txt

On MacOS type:
pip3 install -r requirements.txt

This will install the packages from the requirements.txt for this project.
'''

app = Flask(__name__)
app.config.update(app_config)

ckeditor = CKEditor(app)
Bootstrap5(app)

gravatar = Gravatar(app, 
                    size=50, rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

# TODO: Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
  return db.get_or_404(User, user_id)

# CREATE DATABASE
class Base(DeclarativeBase):
  pass
db = SQLAlchemy(model_class=Base)
db.init_app(app)

# CONFIGURE TABLES
class BlogPost(db.Model):
  __tablename__ = "blog_posts"
  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
  subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
  date: Mapped[str] = mapped_column(String(250), nullable=False)
  body: Mapped[str] = mapped_column(Text, nullable=False)
  img_url: Mapped[str] = mapped_column(String(250), nullable=False)
  user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
  author: Mapped["User"] = relationship(back_populates="posts")
  comments: Mapped[List["Comment"]] = relationship(back_populates="blog")


# TODO: Create a User table for all your registered users. 
class User(UserMixin, db.Model):
  __tablename__ = 'users'
  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  name: Mapped[str] = mapped_column(String(250), nullable=False)
  email: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
  password: Mapped[str] = mapped_column(String(250), nullable=False)
  posts: Mapped[List["BlogPost"]] = relationship(back_populates="author")
  comments: Mapped[List["Comment"]] = relationship(back_populates="user")

class Comment(db.Model):
  __tablename__ = "comments"
  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
  blog_id: Mapped[int] = mapped_column(Integer, ForeignKey("blog_posts.id"))
  user: Mapped["User"] = relationship(back_populates="comments")
  blog: Mapped["BlogPost"] = relationship(back_populates="comments")
  comment: Mapped[str] = mapped_column(String(250), nullable=False)


with app.app_context():
  db.create_all()

def admin_only(f):
  @wraps(f)
  def decorated_function(*args, **kwargs):
    if not current_user.is_authenticated:
      return login_manager.unauthorized()
    if current_user.id != 1:
      return login_manager.unauthorized()

    return f(*args, **kwargs)
  
  return decorated_function

# TODO: Use Werkzeug to hash the user's password when creating a new user.
@app.route('/register', methods=['GET', 'POST'])
def register():
  form = RegisterForm()
  if request.method == 'POST':
    if form.validate_on_submit():
      f = request.form
      res = db.session.execute(db.select(User).where(User.email == f['email']))
      u = res.scalar()

      if u:
        flash('User already exists, please login instead')
        return redirect(url_for('login'))
      
      user = User(
        name=f['name'],
        email=f['email'],
        password=generate_password_hash(f['password'], 'pbkdf2:sha256', 8)
      )
      db.session.add(user)
      db.session.commit()

      login_user(user)

      return redirect(url_for('get_all_posts'))
    
  return render_template("register.html", form=form)


# TODO: Retrieve a user from the database based on their email. 
@app.route('/login', methods=['GET', 'POST'])
def login():
  form = LoginForm()
  del form.name

  if request.method == 'POST':
    if form.validate_on_submit():
      f = request.form
      res = db.session.execute(db.select(User).where(User.email == f['email']))
      user = res.scalar()
      
      if not user:
        flash('Invalid user, please try again')
      elif not check_password_hash(user.password, f['password']):
        flash('Invalid password, please try again')
      else:
        login_user(user)
        return redirect(url_for('get_all_posts'))

  return render_template("login.html", form=form)


@app.route('/logout')
def logout():
  logout_user()
  return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
  result = db.session.execute(db.select(BlogPost).order_by(BlogPost.date.desc()))
  posts = result.scalars().all()
  return render_template("index.html", all_posts=posts)


# TODO: Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>", methods=['GET', 'POST'])
def show_post(post_id):
  requested_post = db.get_or_404(BlogPost, post_id)
  form = CommentForm()
  if request.method == 'POST':
    if not current_user.is_authenticated:
      flash('Please log in to make a comment')
      return redirect(url_for('login'))
    
    if form.validate_on_submit():
      f = request.form
      comment = Comment(
        user=current_user,
        blog=requested_post,
        comment=f['comment']
      )
      db.session.add(comment)
      db.session.commit()

  return render_template("post.html", post=requested_post, form=form)


# TODO: Use a decorator so only an admin user can create a new post
@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
  form = CreatePostForm()
  if form.validate_on_submit():
    new_post = BlogPost(
      title=form.title.data,
      subtitle=form.subtitle.data,
      body=form.body.data,
      img_url=form.img_url.data,
      author=current_user,
      user_id=current_user.id,
      date=date.today().strftime("%B %d, %Y")
    )
    db.session.add(new_post)
    db.session.commit()
    return redirect(url_for("get_all_posts"))
  return render_template("make-post.html", form=form)


# TODO: Use a decorator so only an admin user can edit a post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
  post = db.get_or_404(BlogPost, post_id)
  edit_form = CreatePostForm(
    title=post.title,
    subtitle=post.subtitle,
    img_url=post.img_url,
    author=post.author,
    body=post.body
  )
  if edit_form.validate_on_submit():
    post.title = edit_form.title.data
    post.subtitle = edit_form.subtitle.data
    post.img_url = edit_form.img_url.data
    post.author = current_user
    post.body = edit_form.body.data
    db.session.commit()
    return redirect(url_for("show_post", post_id=post.id))
  return render_template("make-post.html", form=edit_form, is_edit=True)


# TODO: Use a decorator so only an admin user can delete a post
@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
  post_to_delete = db.get_or_404(BlogPost, post_id)
  db.session.delete(post_to_delete)
  db.session.commit()
  return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
  return render_template("about.html")


@app.route("/contact")
def contact():
  return render_template("contact.html")


if __name__ == "__main__":
  app.run(debug=app_config['DEBUG'], port=5004)
