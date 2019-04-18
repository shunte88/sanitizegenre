# sanitizegenre

Quick and dirty utility to fix tagging on my media library of in excess of 12,000 albums, as of mid-April 2019

Missed edits, and issues with Windows 10 tagging facilities have introduced considerable noise within the GENRE tag

In addition many Various Artists rips that where done back in the 2009-2010 period lacked a level of detail on the ARTIST tag

The utility implements a number of metadata cleansing rules to account for these issues as well as a dictionary based transposition mechanism to fix the miriad of GENRE misses

The GENRE transposition data are maintained in a flat file that is initialized at runtime to a dictionary that is then passed to the FLAC metadata class

A little inelegant as it can introduce a little noise, it does however get the job done


Almost pure python3 only requires the metaflac command line utilities and should be cross-platform - the later is untested

