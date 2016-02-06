from math import ceil
from bisect import bisect_left
from logging import debug

from .selection import Interval, Selection
from .contract import post
from .navigation import (
    move_n_wrapped_lines_down, count_wrapped_lines, end_of_wrapped_line)


def _compute_selectionview_post(result, self, old=None, new=None):
    for vbeg, vend in result:
        assert 0 <= vbeg <= vend <= len(self.text)

# TODO: make textview thread-safe
# TODO: find a way to statically prevent thread errors


class TextView:

    """
    Comprise the text features that are shown in the userinterface for a given text
    interval. All the positions in the resulting text are adjusted w.r.t. the text
    concealments that may have been done.

    How does a UI known when a new TextView should be created? A TextView object consists
    of 3 parts w.r.t. to a text interval: - the text (including concealments) - selection
    - highlighting

    So if either the, start, length, text, selection, highlighting or concealment changes,
    the userinterface should create a new TextView object. However, if jus the selection
    of highlighting changes, one only should have to update those. This is currently
    possible by calling compute_highlighting or compute_highlighting.

    Positional computations often have to deal with two kinds of positions: position
    in the original text and in the resulting view text. For clarity we prepend every
    variable containing information relative to the original text with `o` and relative to
    the view text with `v`.

    It should be noted that original positions in origpos_to_viewpos are counted from the
    given offset, i.e. the list is zero-indexed. TODO: make this bijection a separate
    object which hides these ugly and confusing offset differences.
    """

    def __init__(self):
        self.doc = None
        self.width = None
        self.height = None
        self.offset = None

        self.text = None
        self.selection = None
        self.highlighting = None

        self.viewpos_to_origpos = []
        self.origpos_to_viewpos = []

    @staticmethod
    def for_screen(doc, width: int, height: int, offset: int):
        """
        Construct a textview for the given doc starting with (and relative to) position
        start with size of the given length.
        """
        if width <= 0:
            raise ValueError('{} is an invalid width'.format(width))
        if height <= 0:
            raise ValueError('{} is an invalid height'.format(height))
        if offset < 0 or offset > len(doc.text):
            raise ValueError('{} is an invalid offset'.format(offset))

        self = TextView()
        self.doc = doc
        self.width = width
        self.height = height
        self.offset = offset

        self.text, self.origpos_to_viewpos, self.viewpos_to_origpos = (
            self._compute_text_from_view_interval())
        self.selection = self._compute_selection()
        self.highlighting = self._compute_highlighting()

        return self

    @staticmethod
    def for_entire_text(doc, width):
        if width <= 0:
            raise ValueError('{} is an invalid width'.format(width))

        self = TextView()
        self.doc = doc
        self.width = width
        self.offset = 0

        self.text, self.origpos_to_viewpos, self.viewpos_to_origpos = (
            self._compute_text_from_orig_interval(0, len(doc.text)))
        self.selection = self._compute_selection()
        self.highlighting = self._compute_highlighting()

        return self

    def text_as_lines(self):
        """
        Return the text in the textview as a list of lines, where the lines are wrapped
        with self.width.
        """
        result = [line[self.width * i: self.width * (i + 1)]
                  for line in self.text.splitlines()
                  for i in range(ceil(len(line) / self.width))]
        assert len(result) == count_wrapped_lines(self.text, self.width)
        return result

    def _compute_text_from_view_interval(self):
        """
        Compute the concealed text and the corresponding position mapping.
        We don't have any guarantees to the length of the viewtext in terms of the length
        of the original text whatsoever.
        So we can only incrementally try to increase the length of th original text, until
        the viewtext covers the required length.
        Since normally the concealed text is not much (if any) larger, this should not
        lead to accidentally computing a way too large textview.

        Return text and mappings.
        Side effect: none
        """
        width, height = self.width, self.height

        otext = self.doc.text
        obeg = self.offset
        if len(otext) - obeg == 0:
            return '', [0], [0]
        elif len(otext) - obeg < 0:
            raise ValueError('offset is beyond length of text')

        # Length of the sample of the original text that is used to compute the view text
        o_sample_length = 1

        vtext, opos_to_vpos, vpos_to_opos = self._compute_text_from_orig_interval(
            obeg, o_sample_length)
        # The mapping should have synced offsets and be non empty, as o_sample_length > 0 and
        # len(text) > 0
        assert opos_to_vpos[0] >= 0
        while (count_wrapped_lines(vtext, width) < height
               and obeg + o_sample_length < len(otext)):
            o_sample_length *= 2
            vtext, opos_to_vpos, vpos_to_opos = self._compute_text_from_orig_interval(
                obeg, o_sample_length)

        # Everything should be snapped to exactly fit the required length.
        # This is to make textview behave as deterministic as possible, such that potential
        # indexing errors are identified soon.
        last_line = move_n_wrapped_lines_down(vtext, width, 0, height - 1)
        required_length = end_of_wrapped_line(vtext, width, last_line) + 1

        # Assert that we do not have to snap no more then half,
        # otherwise we did too much work
        assert required_length > len(vtext) // 2

        # Extend mappings to allow (exclusive) interval ends to be mapped
        opos_to_vpos.append(len(vtext))
        vpos_to_opos.append(o_sample_length)

        text = vtext[:required_length]
        origpos_to_viewpos = opos_to_vpos[:required_length + 1]
        # FIXME: what should this be?
        # viewpos_to_origpos = vpos_to_opos[:required_length + 1]
        viewpos_to_origpos = vpos_to_opos

        # Some post conditions
        assert len(text) == required_length
        assert len(origpos_to_viewpos) == required_length + 1
        # assert len(viewpos_to_origpos) == required_length + 1

        return text, origpos_to_viewpos, viewpos_to_origpos

    def _compute_text_from_orig_interval(self, obeg, o_sample_length):
        """
        Compute the concealed text and the corresponding position mapping from an interval
        in terms of the original text.

        Return text and mappings.
        Side effect: none
        """
        conceal = self.doc.conceal
        conceal.generate_local_substitutions(obeg, o_sample_length)

        # Construct a sorted list of relevant substitutions
        first_global_subst = bisect_left(conceal.global_substitutions,
                                         (Interval(obeg, obeg), ''))
        last_global_subst = bisect_left(conceal.global_substitutions,
                                        (Interval(obeg + o_sample_length,
                                                  obeg + o_sample_length), ''))
        substitutions = (conceal.local_substitutions
                         + conceal.global_substitutions[first_global_subst:last_global_subst])
        substitutions.sort()

        vtext_builder = []  # Stringbuilder for text to be displayed
        vpos = 0  # Current position in view text, i.e. olength of text builded so far
        opos = obeg  # Current position in original text
        vpos_to_opos = []  # Mapping from view positions to original positions
        # Mapping from original positions (minus offset) to view positions
        opos_to_vpos = []
        otext = self.doc.text

        subst_index = 0
        while opos < obeg + o_sample_length:
            # Add remaining non-concealed text
            if subst_index >= len(substitutions):
                olength = min(o_sample_length - (opos - obeg), len(otext) - (opos - obeg))
                vpos_to_opos.extend(range(opos, opos + olength))
                opos_to_vpos.extend(range(vpos, vpos + olength))
                vtext_builder.append(otext[opos:opos + olength])
                opos += olength
                vpos += olength
                break

            # sbeg and send are in terms of original positions
            (sbeg, send), replacement = substitutions[subst_index]

            # Add non-concealed text
            if sbeg > opos:
                # Bound viewtext by o_sample_length
                olength = min(sbeg - opos, o_sample_length - vpos)
                vpos_to_opos.extend(range(opos, opos + olength))
                opos_to_vpos.extend(range(vpos, vpos + olength))
                vtext_builder.append(otext[opos:opos + olength])
                vpos += olength
                opos += olength
            # Add concealed text
            else:
                vlength = len(replacement)
                olength = send - sbeg
                vpos_to_opos.extend(vlength * [opos])
                opos_to_vpos.extend(olength * [vpos])
                vtext_builder.append(replacement)
                vpos += vlength
                opos += olength
                subst_index += 1

        vtext = ''.join(vtext_builder)

        # Extend mappings to allow (exclusive) interval ends to be mapped
        opos_to_vpos.append(len(vtext))
        vpos_to_opos.append(o_sample_length)

        # Some post conditions
        # assert len(text) == required_length
        # assert len(origpos_to_viewpos) == required_length + 1
        # assert len(viewpos_to_origpos) == required_length + 1

        return vtext, opos_to_vpos, vpos_to_opos

    def _compute_highlighting(self):
        """
        Construct highlighting view.
        The highlighting view is a mapping from each character in the text to a string.
        Since the text positions are positive integers starting from zero, we implement
        this as a list.
        Return highlighting view
        Side effect: None
        """
        highlightingview = []
        for i in range(len(self.text)):
            opos = self.viewpos_to_origpos[i]
            if opos in self.doc.highlighting:
                highlightingview.append(self.doc.highlighting[opos])
            else:
                highlightingview.append('')

        return highlightingview

    @post(_compute_selectionview_post)
    def _compute_selection(self, old=None, new=None):
        """
        Construct selection view.
        Use the opos_to_vpos mapping to derive the selection intervals in the viewport.
        Return selection view
        Side effect: None
        """
        opos_to_vpos = self.origpos_to_viewpos
        o_viewbeg = self.viewpos_to_origpos[0]
        o_viewend = self.viewpos_to_origpos[len(self.text)]

        selectionview = Selection()
        for beg, end in self.doc.selection:
            # Only add selections when they should be visible
            if (beg < o_viewend and o_viewbeg < end
                    # Make sure empty intervals are taken into account, if they are
                    # visible
                    or beg == end == o_viewbeg or beg == end == o_viewend):
                beg = max(beg, o_viewbeg)
                end = min(o_viewend, end)
                vbeg = opos_to_vpos[beg - self.offset]
                # Even though end is exclusive, and may be outside the text, it is being
                # mapped, so we can safely do this
                vend = opos_to_vpos[end] - self.offset
                selectionview.add(Interval(vbeg, vend))

        return selectionview
