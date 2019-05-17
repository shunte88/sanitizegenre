#!/usr/bin/python3

import os
import sys
import argparse
import logging
import subprocess
import glob
from pathlib import Path
from metaflac import MetaFlac
import csv
import re


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
                  replay_gain='+5.500000 dB',
                  isvarious=False,
                  discnumber=0,
                  disctotal=0,
                  tracktotal=0):

    changed = False

    metflac = None

    try:
        metaflac = MetaFlac(filename, genres)
    except:
        logging.error('Exception on {}'.format(filename))
        return

    # for each album processed we should be able to "cache"
    # the genre and use rather than reworking over and over
    flac_comment, changed = metaflac.get_sanitized_vorbis_comment()

    for test_tag in ('ALBUMARTIST', 'ALBUM ARTIST'):
        if test_tag in flac_comment:
            if 'Various' in flac_comment[test_tag][0]:
                if 'Various Production' not in flac_comment[test_tag][0]:
                    flac_comment.pop(test_tag, None)
                    logging.debug('Delete {} Tag'.format(test_tag))
                    changed = True

    # patch for missing year - very noisey!!!
    '''
    if 'YEAR' not in flac_comment:
        if 'DATE' in flac_comment:
            for year in flac_comment['DATE']:
                flac_comment['YEAR'].append(year)
                logging.debug('Adding YEAR Tag')
                changed = True
    '''

    try:

        if isvarious or 'arious' in filename:
            if 'ARTIST' not in flac_comment:
                regex = None
                if '/' in flac_comment['TITLE'][0]:
                    regex = '^(.*)/(.*)$'
                elif '-' in flac_comment['TITLE'][0]:
                    regex = '^(.*)-(.*)$'
                if regex:
                    print('Fix artist and title {}'.format(flac_comment['TITLE'][0]))
                    unpack = re.split(regex, flac_comment['TITLE'][0], maxsplit=2)
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
                    regex = '^(.*)/(.*)$'
                elif '-' in flac_comment['TITLE'][0]:
                    regex = '^(.*)-(.*)$'
                if regex:
                    print('Fix artist and title {}'.format(flac_comment['TITLE'][0]))
                    unpack = re.split(regex, flac_comment['TITLE'][0], maxsplit=2)
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
                    regex = '{}.*/(.*)$'.format(artist)
                elif '-' in flac_comment['TITLE'][0]:
                    regex = '{}.*-(.*)$'.format(artist)
                if regex:
                    print('Fix title {}'.format(flac_comment['TITLE'][0]))
                    unpack = re.split(regex, flac_comment['TITLE'][0], maxsplit=2)
                    flac_comment['TITLE'][0] = unpack[1].strip()
                    logging.debug('Fixing TITLE Tag')
                    changed = True

    except Exception:
        pass

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
                    logging.debug('Adding {} Tag'.format(test_tag))
                    changed = True

    # fix alphabetized stoopids
    regex = '^(.*), (Das|Der|Die|El|La|Las|Le|Les|Los|The)$'
    try:
        for test_tag in ('ARTIST', 'ALBUMARTIST', 'ALBUM ARTIST'):
            if test_tag in flac_comment:
                for i in range(len(flac_comment[test_tag])):
                    m = re.search(regex, flac_comment[test_tag][i])
                    if m:
                        flac_comment[test_tag][i] = '{} {}'.format(m.group(2),
                                                                   m.group(1))
                        logging.debug('Fixing {} Tag'.format(test_tag))
                        changed = True
    except Exception:
        pass

    if 'REPLAYGAIN_TRACK_GAIN' in flac_comment:
        if flac_comment['REPLAYGAIN_TRACK_GAIN'][0] in ('+4.5', '+4.50', '+3.5', '+3.50'):
            flac_comment['REPLAYGAIN_TRACK_GAIN'][0] = replay_gain
            logging.debug('Fix REPLAYGAIN_TRACK_GAIN Tag')
            changed = True
        elif '0' == flac_comment['REPLAYGAIN_TRACK_GAIN'][0]:
            flac_comment.pop('REPLAYGAIN_TRACK_GAIN', None)
            flac_comment['REPLAYGAIN_TRACK_GAIN'].append(replay_gain)
            logging.debug('Fix REPLAYGAIN_TRACK_GAIN Tag')
            changed = True

    if 'COMMENTS' in flac_comment:
        if 'NAD' in flac_comment['COMMENTS'][0]:
            if 'REPLAYGAIN_TRACK_GAIN' not in flac_comment:
                flac_comment['REPLAYGAIN_TRACK_GAIN'].append(replay_gain)
                logging.debug('Add REPLAYGAIN_TRACK_GAIN Tag')
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
            logging.debug('Delete {} Tag'.format(redundant))
            changed = True

    if changed:
        tags_file = '%d.tag' % (os.getpid())
        tf = Path(tags_file)

        if tf.exists():
            tf.unlink()

        logging.info('Rewrite FLAC tags on "{}"'.format(filename))
        text = ''
        for k, v in sorted(flac_comment.items()):
            # dedupe
            if len(v) > 1:
                v = list(set(v))
            for vv in v:
                text += "{}={}\n".format(k, vv)
        tf.write_text(text)
        print(text)

        if tf.exists():
            # metaflac command line
            cmd = 'metaflac --preserve-modtime --no-utf8-convert'
            cmd += ' --remove-all-tags'
            cmd += ' --import-tags-from={} "{}"'.format(tags_file, filename)
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
