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


def fix_flac_tags(filename, genres=None):

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

    if 'arious' in filename:
        if 'ARTIST' not in flac_comment:
            if '/' in flac_comment['TITLE'][0]:
                print('Fix artist and title {}'.format(flac_comment['TITLE'][0]))
                unpack = re.split('^(.*)/(.*)$', flac_comment['TITLE'][0], maxsplit=2)
                flac_comment['ARTIST'].append(unpack[1].strip())
                flac_comment['TITLE'][0] = unpack[2].strip()
                logging.debug('Adding ARTIST Tag')
                changed = True
            elif '-' in flac_comment['TITLE'][0]:
                print('Fix artist and title {}'.format(flac_comment['TITLE'][0]))
                unpack = re.split('^(.*)-(.*)$', flac_comment['TITLE'][0], maxsplit=2)
                flac_comment['ARTIST'].append(unpack[1].strip())
                flac_comment['TITLE'][0] = unpack[2].strip()
                logging.debug('Adding ARTIST Tag')
                changed = True
        elif 'Various' in flac_comment['ARTIST'][0]:
            if '/' in flac_comment['TITLE'][0]:
                print('Fix artist and title {}'.format(flac_comment['TITLE'][0]))
                unpack = re.split('^(.*)/(.*)$', flac_comment['TITLE'][0], maxsplit=2)
                flac_comment['ARTIST'][0] = unpack[1].strip()
                flac_comment['TITLE'][0] = unpack[2].strip()
                logging.debug('Fixing ARTIST and TITLE Tag')
                changed = True
            elif '-' in flac_comment['TITLE'][0]:
                print('Fix artist and title {}'.format(flac_comment['TITLE'][0]))
                unpack = re.split('^(.*)-(.*)$', flac_comment['TITLE'][0], maxsplit=2)
                flac_comment['ARTIST'][0] = unpack[1].strip()
                flac_comment['TITLE'][0] = unpack[2].strip()
                logging.debug('Fixing ARTIST and TITLE Tag')
                changed = True

    if 'REPLAYGAIN_TRACK_GAIN' in flac_comment:
        if flac_comment['REPLAYGAIN_TRACK_GAIN'][0] in ('+4.5', '+4.50', '+3.5', '+3.50'):
            flac_comment['REPLAYGAIN_TRACK_GAIN'][0] = '+4.500000 dB'
            logging.debug('Fix REPLAYGAIN_TRACK_GAIN Tag')
            changed = True
        elif '0' == flac_comment['REPLAYGAIN_TRACK_GAIN'][0]:
            flac_comment.pop('REPLAYGAIN_TRACK_GAIN', None)
            flac_comment['REPLAYGAIN_TRACK_GAIN'].append('+4.500000 dB')
            logging.debug('Fix REPLAYGAIN_TRACK_GAIN Tag')
            changed = True

    if 'COMMENTS' in flac_comment:
        if 'NAD' in flac_comment['COMMENTS'][0]:
            if 'REPLAYGAIN_TRACK_GAIN' not in flac_comment:
                flac_comment['REPLAYGAIN_TRACK_GAIN'].append('+4.500000 dB')
                logging.debug('Add REPLAYGAIN_TRACK_GAIN Tag')
                changed = True

    # dump redundant tags
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
            cmd = 'metaflac --no-utf8-convert'
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
                      genres=genres)


log_file = '/tmp/sanitrizeflactag.log'
parser = argparse.ArgumentParser()

parser.add_argument('--folder', '-f',
                    help='Folder to process',
                    type=str)
parser.add_argument('--genre', '-g',
                    help='Genre Data',
                    type=str)
parser.add_argument('--backup', '-b',
                    help='Backup original files',
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
