import os
import jwt
import dotenv
from passlib.context import CryptContext
from flask import Flask, jsonify, request
from flask.ext.sqlalchemy import SQLAlchemy

dotenv.read_dotenv()

app = Flask(__name__)

#config key
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

# Initialize database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///soundem.db'
db = SQLAlchemy(app)

password_context = CryptContext(['pbkdf2_sha256'])


def make_password(raw_password):
    return password_context.encrypt(raw_password)


def check_password(raw_password, password):
    return password_context.verify(raw_password, password)


def generate_token(payload, secret):
    return jwt.encode(payload, secret)


def decode_token(token, secret):
    try:
        return jwt.decode(token, secret)
    except (jwt.ExpiredSignature, jwt.DecodeError):
        return None


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True)
    password = db.Column(db.String(255))

    def __init__(self, email, password):
        self.email = email
        self.set_password(password)

    @classmethod
    def create(cls, email, password):
        user = User(email=email, password=password)
        db.session.add(user)
        db.session.commit()

        return user

    @classmethod
    def find_by_email(cls, email):
        return User.query.filter_by(email=email).first()

    @classmethod
    def find_by_token(cls, token):
        payload = decode_token(token, app.config['SECRET_KEY'])

        if not payload or 'id' not in payload:
            return None

        return User.query.filter_by(id=payload['id']).first()

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def get_auth_token(self):
        payload = {
            'id': self.id
        }

        return generate_token(payload, app.config['SECRET_KEY'])


class Artist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True)
    bio = db.Column(db.Text())

    def __init__(self, name, bio):
        self.name = name
        self.bio = bio

    @classmethod
    def get_all(cls):
        return Artist.query.all()

    @classmethod
    def get(cls, artist_id):
        return Artist.query.filter_by(id=artist_id).first()


class Album(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))
    artwork_url = db.Column(db.String(255))
    artist_id = db.Column(db.Integer, db.ForeignKey('artist.id'))
    artist = db.relationship('Artist',
                             backref=db.backref('albums', lazy='dynamic'))

    def __init__(self, name, artist, artwork_url=None):
        self.name = name
        self.artist = artist

        if artwork_url:
            self.artwork_url = artwork_url

    @classmethod
    def get_all(cls):
        return Album.query.all()

    @classmethod
    def get(cls, album_id):
        return Album.query.filter_by(id=album_id).first()

    @classmethod
    def total_count(cls):
        return Album.query.count()


class Song(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))
    url = db.Column(db.String(255))
    duration = db.Column(db.Integer)
    album_id = db.Column(db.Integer, db.ForeignKey('album.id'))
    album = db.relationship('Album',
                            backref=db.backref('songs', lazy='dynamic'))

    def __init__(self, name, album, url=None, duration=None):
        self.name = name
        self.album = album

        if url:
            self.url = url

        if duration:
            self.duration = duration

    @classmethod
    def get_all(cls):
        return Song.query.all()

    @classmethod
    def get_favorites(cls, user):
        favorites = Favorite.query.filter_by(user=user)
        song_ids = [favorite.song_id for favorite in favorites]

        if song_ids:
            return Song.filter_by_ids(song_ids)

        return []

    @classmethod
    def filter_by_ids(cls, song_ids):
        return Song.query.filter(Song.id.in_(song_ids))

    @classmethod
    def get(cls, song_id):
        return Song.query.filter_by(id=song_id).first()

    @classmethod
    def total_count(cls):
        return Song.query.count()

    @classmethod
    def total_duration(cls):
        duration = 0

        for song in Song.get_all():
            duration += song.duration

        return duration

    def set_favorite(self, user, favorite):
        if favorite is True:
            return self.favorite(user)

        if favorite is False:
            return self.unfavorite(user)

    def favorite(self, user):
        favorite = Favorite.query.filter_by(song=self, user=user).first()
        is_favorited = True

        if not favorite:
            favorite = Favorite(song=self, user=user)
            db.session.add(favorite)
            db.session.commit()

        return is_favorited

    def unfavorite(self, user):
        favorite = Favorite.query.filter_by(song=self, user=user).first()
        is_favorited = False

        if favorite:
            db.session.delete(favorite)
            db.session.commit()

        return is_favorited

    def is_favorited(self, user):
        favorite = Favorite.query.filter_by(song=self, user=user).first()

        return True if favorite else False


class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User',
                           backref=db.backref('favorites', lazy='dynamic'))
    song_id = db.Column(db.Integer, db.ForeignKey('song.id'))
    song = db.relationship('Song',
                           backref=db.backref('favorites', lazy='dynamic'))

    def __init__(self, song, user):
        self.song = song
        self.user = user

@app.route('/api/v1/artists', methods=['GET'])
def get_artists():
    artists = Artist.get_all()
    results = []
    
    for artist in artists:
        results.append({
            'id': artist.id,
            'name': artist.name,
            'bio': artist.bio,
            'albums':[album.id for album in artist.albums.all()]
        })
        
    return jsonify({'artist': results})

@app.route('/api/v1/artists/<int:artist_id>', methods=['GET'])
#/api/v1/artists/1-100
def get_artist(artist_id):
    artist = Artist.get(artist_id)
    
    if not artist:
        return jsonify({
            'error': 'Artist not found'
        }), 404

    data = {
        'id': artist.id,
        'name': artist.name,
        'bio': artist.bio,
        'albums':[album.id for album in artist.albums.all()]
    }
        
    return jsonify({'artist': data})

@app.route('/api/v1/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    errors = {}

    if not email:
        errors['email'] = 'Email is required.'
    if not password:
        errors['password'] = 'Password is required.'
    if email and User.find_by_email(email):
        errors['email']='Email is already taken.'

    if errors:
        return jsonify({'errors': errors}), 400
        
    user = User.create(email, password)

    user_data = {
        'id': user.id,
        'email': user.email,
        'token': user.get_auth_token()
    }
    return jsonify(user_data), 201

#CHANGE THIS WITH THE COMPLETE ONE
@app.route('/api/v1/songs/<int:song_id>', methods=[''])
@auth_token_required
def song(song_id):
    song = Song.get(song_id)
    is_favorited = None

if not song:
    return jsonify({'error': 'Song not found'})
    if request.method == 'PUT':
        data = request.get_json() or {}
        data_song = data.get('song') or {}
        favorite = data_song.get('favorite')
    if favorite is not None:
        is_favorite = song.set_favorite(g.user, favorite)
        if is_favorited is None:
        is_favorited = song.is_favorited(g.user)

song_data = {
    'id': song.id,
    'name': song.name,
    'almbum': song.album.id,
    'favoritte': i_favorited,
    'duration': song.duration,
    'url': song.url
}

return = jsonify('

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
