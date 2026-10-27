import json
import zipfile

import pytest

import check_bundle as cb
import make_bundle as mb


def workdir(tmp_path, html=None):
    html = html or ('<p>Intro.</p><img src="fees-01-img1.webp" alt="A chart" width="10" height="10">'
                    '<a class="nerdit-file" href="files/L01-S1-fees.csv" download="L01-S1-fees.csv">csv</a>'
                    '<a class="nerdit-file nerdit-file-all" href="files/fees-practice-pack-v1.zip">pack</a>')
    course = {'id': 'fees-course', 'title': 'Fees', 'lessons': [{'id': 'fees-01', 'content': html}]}
    pack = tmp_path / 'pack'
    (pack / 'files').mkdir(parents=True)
    (pack / 'course-fees_output.json').write_text(json.dumps(course), encoding='utf-8')
    (pack / 'files' / 'L01-S1-fees.csv').write_text('fee\n9000\n', encoding='utf-8')
    with zipfile.ZipFile(pack / 'fees-practice-pack-v1.zip', 'w') as z:
        z.writestr('fees-practice-pack-v1/README.txt', 'hi')
    (pack / 'files.manifest.json').write_text(json.dumps({'pack': 'fees-practice-pack-v1.zip', 'files': [
        {'name': 'L01-S1-fees.csv', 'packVersion': 1}]}), encoding='utf-8')
    images = tmp_path / 'images'
    (images / 'upload').mkdir(parents=True)
    (images / 'upload' / 'fees-01-img1.webp').write_bytes(b'RIFF....WEBPVP8 ')
    video = images / 'video'
    video.mkdir()
    (video / 'clips.json').write_text(json.dumps([{'key': 'fees-01-s1', 'title': 'Read fees', 'file': 'clip-01.mp4',
                                                   'youtubeTitle': 'Fees: Read Fees'}]), encoding='utf-8')
    (video / 'description.txt').write_text('Chapters', encoding='utf-8')
    (video / 'thumbnail.jpg').write_bytes(b'\xff\xd8\xff\xe0jpg')
    (video / 'story.mp4').write_bytes(b'mp4')
    return pack / 'course-fees_output.json', pack, images


def test_bundle_has_the_plan_layout_and_no_video_files(tmp_path):
    course, pack, images = workdir(tmp_path)
    path = mb.make_bundle(course, pack, images, out_dir=tmp_path / 'out', slug='fees', version=1)
    assert path.name == 'fees-bundle-v1.zip'
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        assert names == {'course-fees_output.json', 'media/images/fees-01-img1.webp',
                         'media/files/L01-S1-fees.csv', 'media/files/fees-practice-pack-v1.zip',
                         'videos/clips.json', 'videos/description.txt', 'videos/thumbnail.jpg', 'bundle.json'}
        meta = json.loads(z.read('bundle.json'))
        clips = json.loads(z.read('videos/clips.json'))
    assert meta['courseId'] == 'fees-course' and meta['bundleVersion'] == 1 and meta['packVersion'] == 1
    assert set(meta['files']) == names - {'bundle.json'} and len(meta['files']['media/files/L01-S1-fees.csv']['sha256']) == 64
    assert clips == [{'key': 'fees-01-s1', 'title': 'Read fees', 'youtubeTitle': 'Fees: Read Fees', 'youtube': ''}]
    assert cb.check(path) == ([], [])


def test_placed_video_course_keeps_the_plain_course_name(tmp_path):
    course, pack, images = workdir(tmp_path)
    placed = pack / 'course-fees_output.with-images.with-video.json'
    placed.write_bytes(course.read_bytes())
    path = mb.make_bundle(placed, pack, images, out_dir=tmp_path / 'out', slug='fees', version=1)
    with zipfile.ZipFile(path) as z:
        assert 'course-fees_output.json' in z.namelist()
    assert cb.check(path) == ([], [])


def test_missing_media_for_a_link_fails_at_build(tmp_path):
    course, pack, images = workdir(tmp_path)
    (images / 'upload' / 'fees-01-img1.webp').unlink()
    with pytest.raises(ValueError, match='fees-01-img1.webp'):
        mb.make_bundle(course, pack, images, out_dir=tmp_path / 'out', slug='fees', version=1)


def rebuild(path, change):
    with zipfile.ZipFile(path) as z:
        members = {n: z.read(n) for n in z.namelist()}
    change(members)
    with zipfile.ZipFile(path, 'w') as z:
        for n, data in members.items():
            z.writestr(n, data)


def built(tmp_path):
    course, pack, images = workdir(tmp_path)
    return mb.make_bundle(course, pack, images, out_dir=tmp_path / 'out', slug='fees', version=1)


def test_tampered_file_and_unlisted_file_fail(tmp_path):
    path = built(tmp_path)
    rebuild(path, lambda m: m.update({'media/files/L01-S1-fees.csv': b'fee\n1\n', 'media/files/extra.csv': b'a\n'}))
    fails, _ = cb.check(path)
    assert any('L01-S1-fees.csv' in f and 'sha256' in f for f in fails)
    assert any('extra.csv' in f and 'not listed' in f for f in fails)


def test_refused_types_and_bad_content_fail(tmp_path):
    path = built(tmp_path)

    def bad(m):
        m['media/files/L01-S1-run.exe'] = b'MZ'
        m['media/files/fees-practice-pack-v1.zip'] = b'not a zip'
        m['videos/story.mp4'] = b'mp4'
        meta = json.loads(m['bundle.json'])
        for name in ('media/files/L01-S1-run.exe', 'media/files/fees-practice-pack-v1.zip', 'videos/story.mp4'):
            meta['files'][name] = cb.entry(m[name])
        m['bundle.json'] = json.dumps(meta).encode()
    rebuild(path, bad)
    fails, _ = cb.check(path)
    text = '\n'.join(fails)
    assert 'L01-S1-run.exe' in text and 'not allowed' in text
    assert 'fees-practice-pack-v1.zip' in text and 'not a zip' in text
    assert 'story.mp4' in text and 'YouTube' in text


def test_link_to_a_file_not_in_the_bundle_fails(tmp_path):
    path = built(tmp_path)

    def drop(m):
        del m['media/files/L01-S1-fees.csv']
        meta = json.loads(m['bundle.json'])
        del meta['files']['media/files/L01-S1-fees.csv']
        m['bundle.json'] = json.dumps(meta).encode()
    rebuild(path, drop)
    fails, _ = cb.check(path)
    assert any('files/L01-S1-fees.csv' in f and 'not in the bundle' in f for f in fails)


def test_cli_exit_codes(tmp_path):
    course, pack, images = workdir(tmp_path)
    assert mb.main(['--course', str(course), '--pack', str(pack), '--images', str(images), '--slug', 'fees',
                    '--version', '1', '--out-dir', str(tmp_path / 'out')]) == 0
    assert cb.main(['--bundle', str(tmp_path / 'out' / 'fees-bundle-v1.zip')]) == 0
    assert cb.main(['--bundle', str(tmp_path / 'nope.zip')]) == 2


def test_course_without_practice_files_bundles_from_the_workdir(tmp_path):
    course = {'id': 'plain', 'lessons': [{'id': 'p-01', 'content': '<img src="p-01-img1.webp" alt="x">'}]}
    (tmp_path / 'course-plain_output.json').write_text(json.dumps(course), encoding='utf-8')
    (tmp_path / 'images' / 'upload').mkdir(parents=True)
    (tmp_path / 'images' / 'upload' / 'p-01-img1.webp').write_bytes(b'RIFF')
    path = mb.make_bundle(tmp_path / 'course-plain_output.json', tmp_path, tmp_path / 'images',
                          out_dir=tmp_path / 'out', slug='plain', version=1)
    assert cb.check(path) == ([], [])
