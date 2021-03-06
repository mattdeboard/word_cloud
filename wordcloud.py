#!/usr/bin/env python
# Author: Andreas Christian Mueller <amueller@ais.uni-bonn.de>
# (c) 2012
#
# License: MIT

import random

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

import numpy as np
from query_integral_image import query_integral_image

FONT_PATH = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"


def make_wordcloud(words, counts, fname, width, height, font_path=None,
                   margin=5, ranks_only=False, prefer_horiz=0.9):
    """Build word cloud using word counts, store in image.

    Parameters
    ----------
    words : numpy array of strings
        Words that will be drawn in the image.

    counts : numpy array of word counts
        Word counts or weighting of words. Determines the size of the word in
        the final image.
        Will be normalized to lie between zero and one.

    fname : sting
        Output filename. Extension determines image type
        (written with PIL).

    width : int
        Width of the word cloud image.

    height : int
        Height of the word cloud image.

    font_path : string
        Font path to the font that will be used.
        Defaults to DroidSansMono path.

    ranks_only : boolean (default=False)
        Only use the rank of the words, not the actual counts.

    prefer_horiz : float (default=0.90)
        The ratio of times to try horizontal fitting as opposed to vertical.

    Notes
    -----
    Larger Images with make the code significantly slower.
    If you need a large image, you can try running the algorithm at a lower
    resolution and then drawing the result at the desired resolution.

    In the current form it actually just uses the rank of the counts,
    i.e. the relative differences don't matter.
    Play with setting the font_size in the main loop for different styles.

    Colors are used completely at random. Currently the colors are sampled
    from HSV space with a fixed S and V.
    Adjusting the percentages at the very end gives different color ranges.
    Obviously you can also set all at random - haven't tried that.

    """
    if len(counts) <= 0:
        print("We need at least one word to plot a word cloud, got %d."
              % len(counts))

    if font_path is None:
        font_path = FONT_PATH

    # normalize counts
    counts = counts / float(counts.max())
    # sort words by counts
    inds = np.argsort(counts)[::-1]
    counts = counts[inds]
    words = words[inds]
    # create image
    img_grey = Image.new("L", (width, height))
    draw = ImageDraw.Draw(img_grey)
    integral = np.zeros((height, width), dtype=np.uint32)
    img_array = np.asarray(img_grey)
    font_sizes, positions, orientations = [], [], []
    # intitiallize font size "large enough"
    font_size = 1000
    # start drawing grey image
    for word, count in zip(words, counts):
        # alternative way to set the font size
        if not ranks_only:
            font_size = min(font_size, int(100 * np.log(count + 100)))
        while True:
            try:
                # try to find a position
                font = ImageFont.truetype(font_path, font_size)
            except IOError:
                fontfile = FONT_PATH.rsplit('/', 1)[-1]
                raise IOError("Font '%s' not found. Please change 'FONT_PATH' "
                              "to a valid font file path." % fontfile)
            # transpose font optionally
            if random.random() < prefer_horiz:
                orientation = None
            else:
                orientation = Image.ROTATE_90
            transposed_font = ImageFont.TransposedFont(font,
                                                       orientation=orientation)
            draw.setfont(transposed_font)
            # get size of resulting text
            box_size = draw.textsize(word)
            # find possible places using integral image:
            result = query_integral_image(integral, box_size[1] + margin,
                                          box_size[0] + margin)
            if result is not None or font_size == 0:
                break
            # if we didn't find a place, make font smaller
            font_size -= 1

        if font_size == 0:
            # we were unable to draw any more
            break

        x, y = np.array(result) + margin // 2
        # actually draw the text
        draw.text((y, x), word, fill="white")
        positions.append((x, y))
        orientations.append(orientation)
        font_sizes.append(font_size)
        # recompute integral image
        img_array = np.asarray(img_grey)
        # recompute bottom right
        # the order of the cumsum's is important for speed ?!
        partial_integral = np.cumsum(np.cumsum(img_array[x:, y:], axis=1),
                                     axis=0)
        # paste recomputed part into old image
        # if x or y is zero it is a bit annoying
        if x > 0:
            if y > 0:
                partial_integral += (integral[x - 1, y:]
                                     - integral[x - 1, y - 1])
            else:
                partial_integral += integral[x - 1, y:]
        if y > 0:
            partial_integral += integral[x:, y - 1][:, np.newaxis]

        integral[x:, y:] = partial_integral

    # redraw in color
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)
    everything = zip(words, font_sizes, positions, orientations)
    for word, font_size, position, orientation in everything:
        font = ImageFont.truetype(font_path, font_size)
        # transpose font optionally
        transposed_font = ImageFont.TransposedFont(font,
                                                   orientation=orientation)
        draw.setfont(transposed_font)
        draw.text((position[1], position[0]), word,
                  fill="hsl(%d" % random.randint(0, 255) + ", 80%, 50%)")
    img.show()
    img.save(fname)


if __name__ == "__main__":
    import argparse
    import os
    import sys
    from sklearn.feature_extraction.text import CountVectorizer

    parser = argparse.ArgumentParser()
    parser.add_argument('input', nargs='*',
                        help='Source of word data. Can specify either one or '
                        'more filenames or "-" for stdin.')
    parser.add_argument('--skip-missing', '-k', dest='skip',
                        help='Skip any files specified that could not be found,'
                        ' and process with task.', action='store_true')
    parser.add_argument('--stopwords', '-s', dest='stopwords',
                        help='Path to file containing one stopword per line '
                        'or None if no stopwords should be used. '
                        'If not specified, use SciKit-Learn "english" stopword '
                        'dictionary.')
    parser.add_argument('--fontfile', '-f', dest='font_path',
                        help='Path to font file you wish to use. This will '
                        'override the "FONT_PATH" constant.')
    parser.add_argument('--output-name', '-o', dest='output',
                        help='Desired name of PNG output.')
    parser.add_argument('--width', '-W', default=400, type=int,
                        help='Output image width.')
    parser.add_argument('--height', '-H', default=200, type=int,
                        help='Output image height.')
    args = parser.parse_args()
    stopwords = 'english'

    if args.stopwords:
        if args.stopwords == "None":
            args.stopwords = None
        else:
            with open(args.stopwords, "rU") as f:
                stopwords = [i.strip() for i in f.readlines()]

    if "-" in args.input:
        lines = sys.stdin.readlines()
        sources = ['stdin']
    else:
        lines = []
        sources = args.input or ['constitution.txt']
        for s in sources:
            try:
                with open(s) as f:
                    lines.extend(f.readlines())
            except IOError, e:
                if args.skip:
                    print >> sys.stderr, "File '%s' missing. Proceeding..." % s
                    continue
                else:
                    raise IOError(e)

    text = "".join(lines)
    cv = CountVectorizer(min_df=1, decode_error="ignore",
                         stop_words=stopwords, max_features=None)
    counts = cv.fit_transform([text]).toarray().ravel()
    words = np.array(cv.get_feature_names())
    # throw away some words, normalize
    words = words[counts > 1]
    counts = counts[counts > 1]
    output_filename = (args.output or '%s_.png' %
                       (os.path.splitext(os.path.basename(sources[0]))[0]))
    counts = make_wordcloud(words, counts, output_filename,
                            font_path=args.font_path, 
                            width=args.width, height=args.height)

# End of file
