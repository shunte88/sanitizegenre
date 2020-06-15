#!/usr/bin/python3

import os
import sys
import argparse
import logging
import subprocess
import datetime
import glob
from pathlib import Path
from metaflac import MetaFlac
import csv
import re
import contextlib


@contextlib.contextmanager
def ignored(*exceptions):
    try:
        yield
    except exceptions:
        pass


def run_command(cmd, exc=0):

    logging.debug(cmd)
    if 1 == exc:
        try:
            rc = subprocess.run(cmd, shell=True)
            if 0 == rc.returncode:
                return True
        except subprocess.CalledProcessError as err:
            logger.warning(err.output)
            return False
    return False


def fix_flac_tags(filename,
                  genres=None,
                  replay_gain='+8.500000 dB',
                  isvarious=False,
                  discnumber=0,
                  disctotal=0,
                  tracktotal=0):

    changed = False
    vinyl_rip = '24bVR'
    bad_vinyl_tag = '24Vbr'

    today = datetime.date.today()
    metflac = None

    try:
        metaflac = MetaFlac(filename, genres)
    except:
        logging.error(f'Exception on {filename}')
        return

    # for each album processed we should be able to "cache"
    # the genre and use rather than reworking over and over
    flac_comment, changed, ID3_tags = metaflac.get_sanitized_vorbis_comment()

    if ID3_tags:
        changed = True

    if 0 == isvarious:
        with ignored(KeyError, IndexError):
            isvarious = ( \
                (int('Y' == flac_comment['COMPILATION'][0])) or \
                (int('1' == flac_comment['COMPILATION'][0])))

    for test_tag in ('ALBUMARTIST', 'ALBUM ARTIST'):
        if test_tag in flac_comment:
            if 'Various' in flac_comment[test_tag][0] or 1 == isvarious:
                if 'Various Production' not in flac_comment[test_tag][0]:
                    flac_comment.pop(test_tag, None)
                    logging.debug(f'Delete {test_tag} Tag')
                    changed = True

    try:

        if 1 == isvarious or 'arious' in filename:
            if 'ARTIST' not in flac_comment:
                regex = None
                if '/' in flac_comment['TITLE'][0]:
                    regex = r'^(.*)/(.*)$'
                elif ':' in flac_comment['TITLE'][0]:
                    regex = r'^(.*):(.*)$'
                elif '_' in flac_comment['TITLE'][0]:
                    regex = r'^(.*)_(.*)$'
                elif '-' in flac_comment['TITLE'][0]:
                    regex = r'^(.*)-(.*)$'
                if regex:
                    print(f"Fix artist and title {flac_comment['TITLE'][0]}")
                    unpack = re.split(regex,
                                      flac_comment['TITLE'][0],
                                      maxsplit=2)
                    artist = unpack[1].strip()
                    title = unpack[2].strip()
                    if len(artist) < 3:
                        # we have {n} artist title
                        # regex is smart so unlikely
                        unpack = re.split(regex, title, maxsplit=2)
                        artist = unpack[1].strip()
                        title = unpack[2].strip()
                    flac_comment['ARTIST'].append(artist)
                    flac_comment['TITLE'][0] = title
                    logging.debug('Adding ARTIST Tag')
                    changed = True

            elif 'arious' in flac_comment['ARTIST'][0]:
                regex = None
                if '/' in flac_comment['TITLE'][0]:
                    regex = r'^(.*)/(.*)$'
                elif '_' in flac_comment['TITLE'][0]:
                    regex = r'^(.*)_(.*)$'
                elif '-' in flac_comment['TITLE'][0]:
                    regex = r'^(.*)-(.*)$'
                if regex:
                    print(f"Fix artist and title {flac_comment['TITLE'][0]}")
                    unpack = re.split(regex,
                                      flac_comment['TITLE'][0],
                                      maxsplit=2)
                    artist = unpack[1].strip()
                    title = unpack[2].strip()
                    if len(artist) < 3:
                        # we have {n} artist title
                        # regex is smart so unlikely
                        unpack = re.split(regex, title, maxsplit=2)
                        artist = unpack[1].strip()
                        title = unpack[2].strip()
                    flac_comment['ARTIST'][0] = artist
                    flac_comment['TITLE'][0] = title
                    logging.debug('Fixing ARTIST and TITLE Tag')
                    changed = True
            elif flac_comment['ARTIST'][0] in flac_comment['TITLE'][0]:
                regex = None
                # need to escape control characters (regex)
                artist = re.escape(flac_comment['ARTIST'][0])
                if '/' in flac_comment['TITLE'][0]:
                    regex = f'{artist}.*/(.*)$'
                elif '_' in flac_comment['TITLE'][0]:
                    regex = f'{artist}.*_(.*)$'
                elif '-' in flac_comment['TITLE'][0]:
                    regex = f'{artist}.*-(.*)$'
                if regex:
                    print(f"Fix title {flac_comment['TITLE'][0]}")
                    unpack = re.split(regex,
                                      flac_comment['TITLE'][0],
                                      maxsplit=2)
                    flac_comment['TITLE'][0] = unpack[1].strip()
                    logging.debug('Fixing TITLE Tag')
                    changed = True

    except Exception:
        pass


    if 'PERFORMER' not in flac_comment:
        if 'ARTIST' in flac_comment:
            flac_comment['PERFORMER'].append(flac_comment['ARTIST'][0])
            logging.debug('Adding PERFORMER Tag')
            changed = True
    elif "" == flac_comment['PERFORMER'][0].strip():
        if 'ARTIST' in flac_comment:
            flac_comment.pop('PERFORMER', None)
            flac_comment['PERFORMER'].append(flac_comment['ARTIST'][0])
            logging.debug('Adding PERFORMER Tag')
            changed = True

    # fix disktotal, disknumber tag typo

    for test_tag in ('DISKNUMBER', 'DISKTOTAL'):
        if test_tag in flac_comment:
            new_tag = test_tag.replace('K', 'C')
            if new_tag not in flac_comment:
                value = '01'
                with ignored(KeyError, ValueError):
                    value = str(int(flac_comment[test_tag][0])).zfill(2)
                flac_comment[new_tag].append(value)
                logging.debug(f'Adding {new_tag} Tag')
            logging.debug(f'Cleanup {test_tag} Tag')
            flac_comment.pop(test_tag, None)
            changed = True

    if (discnumber+disctotal+tracktotal) > 0:
        for test_tag in ('DISCNUMBER', 'DISCTOTAL', 'TRACKTOTAL'):
            if test_tag not in flac_comment:
                if 'DISCNUMBER' == test_tag:
                    value = discnumber
                elif 'DISCTOTAL' == test_tag:
                    value = disctotal
                else:
                    value = tracktotal
                if value > 0:
                    flac_comment[test_tag].append(value)
                    logging.debug(f'Adding {test_tag} Tag')
                    changed = True

    # fix alphabetized stoopids
    regex = r'^(.*), (Das|Der|Die|El|La|Las|Le|Les|Los|The)$'

    for test_tag in ('ARTIST', 'ALBUMARTIST', 'ALBUM ARTIST'):
        if test_tag in flac_comment:
            for i, value in enumerate(flac_comment[test_tag]):
                m = re.search(regex, value, re.IGNORECASE)
                if m:
                    flac_comment[test_tag][i] = f'{m.group(2).capitalize()} {m.group(1)}'
                    logging.debug(f'Fixing {test_tag} Tag')
                    changed = True

    if 'REPLAYGAIN_TRACK_GAIN' in flac_comment:
        if flac_comment['REPLAYGAIN_TRACK_GAIN'][0] in ('+4.5',
                                                        '+4.50',
                                                        '+3.5',
                                                        '+3.50'):
            flac_comment['REPLAYGAIN_TRACK_GAIN'][0] = replay_gain
            logging.debug('Fix REPLAYGAIN_TRACK_GAIN Tag')
            changed = True
        elif '0' == flac_comment['REPLAYGAIN_TRACK_GAIN'][0]:
            flac_comment.pop('REPLAYGAIN_TRACK_GAIN', None)
            flac_comment['REPLAYGAIN_TRACK_GAIN'].append(replay_gain)
            logging.debug('Fix REPLAYGAIN_TRACK_GAIN Tag')
            changed = True

    with ignored(KeyError, IndexError):
        for fixem in ('ALBUM','TITLE'):
            if fixem in flac_comment:
                if bad_vinyl_tag in flac_comment[fixem][0]:
                    flac_comment[fixem][0] = flac_comment[fixem][0].replace(bad_vinyl_tag,vinyl_rip)
                    logging.debug(f'Fix {fixem} typo.')
                    changed = True

    with ignored(KeyError, IndexError):
        if 'FFZ' in flac_comment['COMMENTS'][0]:
            logging.debug('Default COMMENT Tag')
            flac_comment.pop('COMMENTS', None)
            changed = True
        if 'FFZ' in flac_comment['COMMENT'][0]:
            logging.debug('Default COMMENT Tag')
            flac_comment.pop('COMMENT', None)
            changed = True
        if 'NAD' in flac_comment['COMMENT'][0]:
            if 'REPLAYGAIN_TRACK_GAIN' not in flac_comment:
                flac_comment['REPLAYGAIN_TRACK_GAIN'].append(replay_gain)
                logging.debug('Add REPLAYGAIN_TRACK_GAIN Tag')
                changed = True
        if vinyl_rip in flac_comment['ALBUM'][0]:
            if 'REPLAYGAIN_TRACK_GAIN' not in flac_comment:
                flac_comment['REPLAYGAIN_TRACK_GAIN'].append(replay_gain)
                logging.debug('Add REPLAYGAIN_TRACK_GAIN Tag')
                changed = True
        if 'inyl' in flac_comment['COMMENT'][0] or 'Digitally' in flac_comment['COMMENT'][0]:
            if 'REPLAYGAIN_TRACK_GAIN' not in flac_comment:
                flac_comment['REPLAYGAIN_TRACK_GAIN'].append(replay_gain)
                logging.debug('Add REPLAYGAIN_TRACK_GAIN Tag')
                changed = True
            flac_comment.pop('COMMENT', None)
            changed = True
        if 'inyl' in flac_comment['COMMENTS'][0] or 'Digitally' in flac_comment['COMMENTS'][0]:
            if 'REPLAYGAIN_TRACK_GAIN' not in flac_comment:
                flac_comment['REPLAYGAIN_TRACK_GAIN'].append(replay_gain)
                logging.debug('Add REPLAYGAIN_TRACK_GAIN Tag')
                changed = True
            flac_comment.pop('COMMENTS', None)
            changed = True

    with ignored(KeyError, IndexError):
        if 'inyl' in flac_comment['COMMENTS'][0] or \
        'Digitally' in flac_comment['COMMENTS'][0] or \
        'inyl' in flac_comment['COMMENT'][0] or \
        'Digitally' in flac_comment['COMMENT'][0]:
            if 'REPLAYGAIN_TRACK_GAIN' not in flac_comment:
                flac_comment['REPLAYGAIN_TRACK_GAIN'].append(replay_gain)
                logging.debug('Add REPLAYGAIN_TRACK_GAIN Tag')
                changed = True
            flac_comment.pop('COMMENTS', None)
            changed = True

    # dump redundant or problematic tags
    for redundant in ('REPLAYGAIN_ALBUM_GAIN',
                      'REPLAYGAIN_ALBUM_PEAK',
                      'REPLAYGAIN_TRACK_PEAK',
                      'UNSYNCEDLYRICS',
                      'CONTACT',
                      'LOCATION',
                      'GROUPING'):
        if redundant in flac_comment:
            flac_comment.pop(redundant, None)
            logging.debug(f'Delete {redundant} Tag')
            changed = True

    # add signature if not present
    if 'COMMENT' not in flac_comment:
        flac_comment['COMMENT'].append(f'FixFlac {today}')
        logging.debug('Adding COMMENT Tag')
        changed = True
    else:
        with ignored(KeyError, IndexError):
            for junker in ('Saracon', 'PS3', 'AccurateRip', 'Tagged By', 'Beers', 'Digitally', 'Vinyl'):
                if junker in flac_comment['COMMENT'][0]:
                    print(f"---------------> {flac_comment['COMMENT'][0]}")
                    logging.debug(f'Fix multi-line COMMENT Tag - {junker}')
                    flac_comment.pop('COMMENT', None)
                    flac_comment['COMMENT'].append(f'FixFlac {today}')
                    changed = True


    for fix_tag in ('DATE', 'YEAR'):
        if fix_tag in flac_comment:
            if len(flac_comment[fix_tag]) > 1:
                flac_comment[fix_tag] = flac_comment[fix_tag][:1]
                logging.debug(f'Cleanup {fix_tag} Tag')
                changed = True

    if changed:
        tags_file = '%d.tag' % (os.getpid())
        tf = Path(tags_file)

        if tf.exists():
            tf.unlink()

        logging.info(f'Rewrite FLAC tags on "{filename}"')
        text = ''
        for k, v in sorted(flac_comment.items()):
            # dedupe
            if len(v) > 1:
                v = list(set(v))
            for vv in v:
                if (("\n" in vv)or("\r" in vv)):
                    vv = vv.replace('\r\n', ' ')
                    vv = vv.replace('\n', ' ')
                    vv = vv.replace('\r', ' ')
                text += f"{k}={vv}\n"
        tf.write_text(text)
        print(text)

        if tf.exists():

            if ID3_tags:
                cmd = f'id3v2 --delete-all "{filename}"'
                print(cmd)
                run_command(cmd, 1)

            # metaflac command line
            cmd = 'metaflac --preserve-modtime --no-utf8-convert'
            cmd += ' --remove-all-tags'
            cmd += f' --import-tags-from={tags_file} "{filename}"'
            run_command(cmd, 1)
            # cleanup
            tf.unlink()


def main(args):

    genres = dict()
    if args.genre:
        with open(args.genre) as f:
            for line in f:
                if line.strip() and not line.strip().startswith('#'):
                    k, v = line.strip().split('|')
                    genres[k] = v

    pathlist = Path(args.folder).glob('*/*.flac')
    for path in sorted(pathlist):
        fix_flac_tags(str(path),
                      genres=genres,
                      isvarious=args.various,
                      discnumber=args.discnumber,
                      disctotal=args.disctotal,
                      tracktotal=args.tracktotal)


log_file = '/tmp/sanitrizeflactag.log'
parser = argparse.ArgumentParser()

parser.add_argument('--folder', '-f',
                    help='Folder to process',
                    type=str)
parser.add_argument('--genre', '-g',
                    help='Genre Data',
                    type=str)
parser.add_argument('--various', '-v',
                    help='Various Artists',
                    type=bool,
                    default=False)
parser.add_argument('--backup', '-b',
                    help='Backup original files',
                    type=int,
                    default=0)
parser.add_argument('--discnumber', '-n',
                    help='Disc Number',
                    type=int,
                    default=0)
parser.add_argument('--disctotal', '-d',
                    help='Disc Total',
                    type=int,
                    default=0)
parser.add_argument('--tracktotal', '-t',
                    help='Track Total',
                    type=int,
                    default=0)


args = parser.parse_args()

if __name__ == "__main__":

    log_format = '%(asctime)s %(levelname)-8s %(message)s'
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter(log_format)
    console.setFormatter(formatter)
    logging.basicConfig(level=logging.DEBUG,
                        format=log_format,
                        datefmt='%m-%d-%y %H:%M',
                        filename=log_file,
                        filemode='a')

    logging.getLogger('').addHandler(console)

    main(args)

sys.exit(0)
