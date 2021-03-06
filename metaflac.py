import io
import struct
import codecs
from collections import defaultdict

# https://xiph.org/flac/format.html#metadata_block
# All numbers used in a FLAC bitstream are integers; 
# there are no floating-point representations. 
# All numbers are big-endian coded. 
# All numbers are unsigned unless otherwise specified.


class MetaFlacException(Exception):
    pass


def _read(file, nbytes):  # helper function to check if we haven't reached EOF
    b = file.read(nbytes)
    if len(b) < nbytes:
        raise MetaFlacException('Unexpected end of file')
    return b


class MetaFlac:

    def __init__(self, filename, genres=None):
        self.__block_streaminfo = None
        self.__block_application = None
        self.__block_seektable = None
        self.__block_vorbis_comment = None
        self.__block_cuesheet = None
        self.__block_picture = None
        self.__ID3_tags = False

        self.genres = genres
        self.filename = filename

        with io.open(filename, 'rb') as file:

            self.__parse_marker(file)

            last = 0
            while not last:
                last, block_type, size = self.__parse_block_header(file.read(4))

                if block_type == 0:
                    self.__block_streaminfo = file.read(size)

                elif block_type == 1:
                    file.read(size)

                elif block_type == 2:
                    self.__block_application = file.read(size)

                elif block_type == 3:
                    self.__block_seektable = file.read(size)

                elif block_type == 4:
                    self.__block_vorbis_comment = file.read(size)

                elif block_type == 5:
                    self.__block_cuesheet = file.read(size)

                elif block_type == 6:
                    self.__block_picture = file.read(size)

                elif block_type < 127:
                    print(block_type)
                    raise NotImplementedError('reserved')

                else:
                    raise NotImplementedError('invalid, to avoid confusion with a frame sync code')

    def __parse_marker(self, file):
        # check for ID3 - rare but annoying
        block = file.read(3)
        if block == b'ID3':
            self.__ID3_tags = True
            # jump the ID3 tag if it exists
            file.seek(0)  # reset
            header = struct.unpack('3sBBB4B', _read(file, 10))
            size = self._calc_size(header[4:8], 7)
            end_pos = file.tell() + size
            file.seek(end_pos, os.SEEK_SET)  # skip ID3 tags - ??? good tag data ???
            block = file.read(4)  # after ID3 we should be on fLaC
        else:
            file.seek(0)
            block = file.read(4)

        # "fLaC", the FLAC stream marker in ASCII
        if block != b'fLaC':
            raise MetaFlacException(f'{block} is not valid flac header on {self.filename}')

    def __parse_block_header(self, block):
        unpacked = struct.unpack('>I', block)[0]
        # Last-metadata-block flag: '1' if this block is the last
        # metadata block before the audio blocks, '0' otherwise.
        last = unpacked >> 31
        block_type = unpacked >> 24 & 0x7f
        # Length (in bytes) of metadata to follow.
        size = unpacked & 0x00ffffff
        return last, block_type, size

    def get_streaminfo(self):
        if not self.__block_streaminfo:
            return None
        streaminfo = dict()
        block = self.__block_streaminfo
        # 16bits The minimum block size (in samples) used in the stream.
        streaminfo['minimum_blockSize'] = struct.unpack('>H', block[0:2])[0]
        # 16bits The maximum block size (in samples) used in the stream.
        streaminfo['maximum_blockSize'] = struct.unpack('>H', block[2:4])[0]
        # 24bits The minimum frame size (in bytes) used in the stream.
        streaminfo['minimum_frameSize'] = struct.unpack('>I', '\x00' + block[4:7])[0]
        # 24bits The maximum frame size (in bytes) used in the stream.
        streaminfo['maximum_frameSize'] = struct.unpack('>I', '\x00' + block[7:10])[0]
        unpacked = struct.unpack('>Q', block[10:18])[0]
        # (36bits) Total samples in stream.
        streaminfo['total_samples_in_stream'] = unpacked & 0xfffffffff
        unpacked = unpacked >> 36
        # (5bits) Bits per sample.
        streaminfo['bits_per_sample'] = (unpacked & 0x1f) + 1
        unpacked = unpacked >> 5
        # (3bits) Number of channels.
        streaminfo['number_of_channels'] = (unpacked & 0x7) + 1
        # (20bits) Sample rate in Hz.
        streaminfo['sample_rate'] = unpacked >> 3
        # (128bits) MD5 signature of the unencoded audio data.
        streaminfo['md5'] = block[18:34]
        return streaminfo

    def get_application(self):
        # The ID request should be 8 hexadecimal digits
        if not self.__block_application:
            return None
        application = dict()
        block = self.__block_application
        # (32bits) Registered application ID.
        application['registered_id'] = hex(struct.unpack('>I', block[0:4])[0])
        application['data'] = block[4:]
        return application

    def get_seektable(self):
        if not self.__block_seektable:
            return None
        seektable = list()
        for i in xrange(0, len(self.__block_seektable), 18):
            # (64bits) Sample number of first sample in the target frame,
            # or 0xFFFFFFFFFFFFFFFF for a placeholder point.
            number = struct.unpack('>Q', self.__block_seektable[i:i+8])[0]
            # (64bits) Offset (in bytes) from the first byte of the first frame
            # header to the first byte of the target frame's header.
            offset = struct.unpack('>Q', self.__block_seektable[i+8:i+16])[0]
            # (16bits) Number of samples in the target frame.
            samples = struct.unpack('>H', self.__block_seektable[i+16:i+18])[0]
            seekpoint = (number, offset, samples)
            seektable.append(seekpoint)
        return seektable

    def get_picture(self):
        if not self.__block_picture:
            return None
        picture = dict()
        block = self.__block_picture
        # (32bits) The picture type according to the ID3v2 APIC frame.
        picture['picture_type'] = struct.unpack('>I', block[0:4])[0]
        # (32bits) The length of the MIME type string in bytes.
        length = struct.unpack('>I', block[4:8])[0]
        # (n*8bites) The MIME type string.
        picture['mime'] = block[8:8+length]
        block = block[8+length:]
        length = struct.unpack('>I', block[0:4])[0] # (32bits) The length of the description string in bytes.
        picture['description'] = codecs.decode(block[4:4+length], 'UTF-8') # (n*8bites) The description of the picture, in UTF-8.
        block = block[4+length:]
        picture['width'] = struct.unpack('>I', block[0:4])[0] # (32bits) The width of the picture in pixels.
        picture['height'] = struct.unpack('>I', block[4:8])[0] # (32bits) The height of the picture in pixels.
        picture['depth'] = struct.unpack('>I', block[8:12])[0]# (32bits) The color depth of the picture in bits-per-pixel.
        picture['nOfcolors'] = struct.unpack('>I', block[12:16])[0] # (32bits) For indexed-color pictures (e.g. GIF), the number of colors used, or 0 for non-indexed pictures.
        length = struct.unpack('>I', block[16:20])[0] # (32bits) The length of the picture data in bytes.
        picture['data'] = block[20:20+length] # (n*8bites) The binary picture data.
        return picture

    def __sanitize_genre(self, tags):
        if self.genres:
            try:
                ret = self.genres[tags]
                return ret, (ret != tags)
            except KeyError:
                print('>>{}<<'.format(tags))
                return tags, False
        else:
            return tags, False

    def get_sanitized_vorbis_comment(self):
        # https://www.xiph.org/vorbis/doc/v-comment.html
        # note that the 32-bit field lengths are little-endian coded according
        # to the vorbis spec, as opposed to the usual big-endian coding of
        # fixed-length integers in the rest of FLAC.
        if not self.__block_vorbis_comment:
            return None

        # support multiple entries for genre, artist etc
        vorbis_comment = defaultdict(list)
        block = self.__block_vorbis_comment
        # (32bits) vendor_length
        vendorLength = struct.unpack('I', block[0:4])[0]
        vendor = codecs.decode(block[4:4+vendorLength], 'UTF-8')
        block = block[4+vendorLength:]
        # (32bits) user_comment_list_length
        userCommentListLength = struct.unpack('I', block[0:4])[0]
        block = block[4:]
        expanded = False
        for i in range(userCommentListLength):
            length = struct.unpack('I', block[0:4])[0]
            user_comment = codecs.decode(block[4:4+length], 'UTF-8')
            block = block[4+length:]
            if '=' in user_comment:
                key, value = user_comment.split('=', 1)
                key = key.upper()

                # sanitize genre via the maintained dictionary
                if 'GENRE' == key:
                    value, test = self.__sanitize_genre(value)
                    # if genre transposed/cleansed then flag
                    if test:
                        print(value)
                        expanded = True

                # support multiple entries for genre, artist etc
                if ';' in value:
                    for value in value.split(';'):
                        expanded = True
                        value = value.strip()
                        if value:
                            vorbis_comment[key].append(value)
                else:
                    vorbis_comment[key].append(value)
        return vorbis_comment, expanded, self.__ID3_tags

    def _calc_size(self, bytestr, bits_per_byte):
        # length of some mp3 header fields is described by 7 or 8-bit-bytes
        return reduce(lambda accu, elem: (accu << bits_per_byte) + elem, bytestr, 0)
