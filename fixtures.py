import json

from app import db, Artist, Album, Song


if __name__ == '__main__':
    fixture_path = 'sample.json'

    print "Dropping tables..."
    db.drop_all()

    print "Creating tables..."
    db.create_all()

    with open(fixture_path) as fixture_file:
        fixtures = json.load(fixture_file)

    for artist in fixtures:
        print 'Creating artist: {}'.format(artist['name'])
        _artist = Artist(
            name=artist['name'],
            bio=artist['bio']
        )

        db.session.add(_artist)

        for album in artist['albums']:
            print ' Creating album: {}'.format(album['name'])
            _album = Album(
                name=album['name'],
                artwork_url=album['artwork_url'],
                artist=_artist
            )

            db.session.add(_album)

            for song in album['songs']:
                print '     Creating song: {}'.format(song['name'])
                _song = Song(name=song['name'], album=_album,
                             url=song['url'], duration=song['duration'])

                db.session.add(_song)

        db.session.commit()