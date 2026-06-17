import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

app = Flask(__name__)

# --- 1. 基礎配置 (Speed & Anti-Sensitive Settings) ---
app.secret_key = 'kHss_Forum_#2026_Secure_String_987654321'
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# 圖片上傳配置
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 雲端 / 本地資料庫智慧切換
db_url = os.environ.get('DATABASE_URL')
if db_url:
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'database.db')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# --- 2. 簡化版資料庫模型 (No Account System) ---
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    image_url = db.Column(db.String(200), nullable=True)
    
    # Emoji 高速計數器
    like_count = db.Column(db.Integer, default=0)
    love_count = db.Column(db.Integer, default=0)
    haha_count = db.Column(db.Integer, default=0)
    
    comments = db.relationship('Comment', backref='post', cascade="all, delete-orphan", lazy='dynamic')

    @property
    def trending_score(self):
        emoji_total = self.like_count + self.love_count + self.haha_count
        return (emoji_total * 2) + (self.comments.count() * 3)


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)


# --- 3. 路由實作 (Routes) ---

# 🏠 首頁（自動熱門排序）
@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('q', type=str)
    
    query = Post.query
    if search_query:
        query = query.filter(Post.content.like(f'%{search_query}%') | Post.title.like(f'%{search_query}%'))
        
    all_posts = query.all()
    all_posts.sort(key=lambda x: (x.trending_score, x.timestamp), reverse=True)
    
    per_page = 10
    start = (page - 1) * per_page
    end = start + per_page
    paginated_posts = all_posts[start:end]
    
    class DummyPagination:
        def __init__(self, page, total_items, per_page):
            self.page = page
            self.total = total_items
            self.per_page = per_page
            self.has_prev = page > 1
            self.has_next = end < total_items
            self.prev_num = page - 1
            self.next_num = page + 1
            
    pagination = DummyPagination(page, len(all_posts), per_page)
    return render_template('index.html', posts=paginated_posts, pagination=pagination, search_query=search_query)


# 📝 建立貼文
@app.route('/create_post', methods=['GET', 'POST'])
def create_post():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        
        image_url = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_url = f"uploads/{filename}"

        if not content or content.strip() == '':
            flash('貼文內容不能為空！', 'danger')
            return render_template('create_post.html')

        try:
            hk_now = datetime.utcnow() + timedelta(hours=8)
            new_post = Post(title=title, content=content, image_url=image_url, timestamp=hk_now)
            db.session.add(new_post)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash('發帖失敗，請稍後再試！', 'danger')
            return render_template('create_post.html')

        return redirect(url_for('index'))
    return render_template('create_post.html')


# 🎭 點擊 Emoji 
@app.route('/post/<int:post_id>/react', methods=['POST'])
def react_post(post_id):
    post = Post.query.get_or_404(post_id)
    emoji_type = request.form.get('emoji')
    if emoji_type == '👍': post.like_count += 1
    elif emoji_type == '❤️': post.love_count += 1
    elif emoji_type == '😂': post.haha_count += 1
    db.session.commit()
    return redirect(request.referrer or url_for('index'))


# 🔍 貼文詳細頁面
@app.route('/post/<int:post_id>')
def post_detail(post_id):
    post = Post.query.get_or_404(post_id)
    comments = post.comments.order_by(Comment.timestamp.asc()).all()
    return render_template('post_detail.html', post=post, comments=comments)


# 💬 新增留言
@app.route('/post/<int:post_id>/comment', methods=['POST'])
def add_comment(post_id):
    content = request.form.get('content')
    if content and content.strip() != '':
        hk_now = datetime.utcnow() + timedelta(hours=8)
        new_comment = Comment(content=content.strip(), post_id=post_id, timestamp=hk_now)
        db.session.add(new_comment)
        db.session.commit()
    return redirect(url_for('post_detail', post_id=post_id))


# 🔒 站長專用：隱藏暗號刪除貼文功能（處理敏感內容）
@app.route('/delete_post/<int:post_id>/<string:secret_key>', methods=['GET', 'POST'])
def delete_post(post_id, secret_key):
    MY_SECRET_KEY = "KHSS_Delete_Secret_2026"  # 💡 你的專屬站長暗號
    if secret_key != MY_SECRET_KEY:
        return "權限不足，密鑰錯誤！", 403
        
    post = Post.query.get_or_404(post_id)
    try:
        db.session.delete(post)
        db.session.commit()
        flash('已成功利用站長權限下架該違規敏感貼文。', 'success')
        return redirect(url_for('index'))
    except Exception as e:
        db.session.rollback()
        return f"刪除失敗: {e}", 500


with app.app_context():
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)