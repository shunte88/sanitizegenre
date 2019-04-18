# sanitizegenre

Quick and dirty utility to fix tagging on my media library of in excess of 12,000 albums

Missed edits and issues with Windows 10 tagging facilities introduced considerable noise within the GENRE tagging

In addition many Various Artists rips that where done back in the 2009-2010 period lacked a level of detail on the ARTIST tag

The utility implemenst a number of data cleansing rules to account for these issues as well as a dictionary based transposition mechanism to fix the miriad of GENRE misses


Almost pure python3 only requires the metaflac command line utilities and should be cross-platform - the later is untested

