"""Sequence string decoder for the motor-controller command format.

Translates a compact human-readable sequence string (e.g. ``"2(100ms L 50ms)"``
) into the pipe-delimited list consumed by the motor-controller protocol.
"""

import re


class sequence_decoder:
    """Decode a compact sequence string into a motor-controller command list.

    The input syntax supports:

    - **Numeric tokens** with optional time units (``ms``, ``s``, ``us`` / ``µs``,
      ``m``) and an optional trailing letter (e.g. ``100ms``, ``50L``).
    - **Repetition** via ``N(…)`` notation — ``4(AB)`` expands to ``ABABABAB``.
    - **Bracketed integers** ``[N]`` that map to the ``N!`` step command.
    - **``T``** as a literal trigger token.

    The decoded list is prefixed with the acquisition count and inter-acquisition
    delay before the sequence tokens::

        [NbAcqu, '|', TimeBetweenAcqu, '|', token, token, …]

    Attributes:
        mc: Motor-controller handle (unused internally; reserved for the caller).
        NbAcqu (int): Number of acquisitions prepended to every decoded list.
        TimeBetweenAcqu (int | float): Delay between acquisitions (ms) prepended
            to every decoded list.
    """

    def __init__(self, mc=None, NbAcqu: int = 1, TimeBetweenAcqu: int = 0) -> None:
        """Initialise the decoder with acquisition metadata.

        Args:
            mc: Motor-controller handle forwarded verbatim to ``self.mc``.
                Not used by the decoder itself.
            NbAcqu: Number of acquisitions to embed at the start of the decoded
                list.
            TimeBetweenAcqu: Delay between acquisitions in milliseconds to embed
                at the start of the decoded list.
        """
        self.mc = mc
        self.NbAcqu = NbAcqu
        self.TimeBetweenAcqu = TimeBetweenAcqu

    def expand_parentheses(self, sequence: str) -> str:
        """Expand all ``N(…)`` repetition groups in *sequence*.

        Repeatedly applies the substitution ``N(content)`` → ``content`` × N
        until no further ``N(…)`` patterns remain, which handles nested groups
        from the inside out.

        Args:
            sequence: Raw sequence string potentially containing ``N(…)``
                repetition groups, e.g. ``"2(A3(B))"``.

        Returns:
            The fully expanded string with all repetition groups replaced by
            their literal content, e.g. ``"ABBBABBB"``.
        """
        pattern = re.compile(r'(\d+)\(([^()]+)\)')
        while re.search(pattern, sequence):
            sequence = re.sub(pattern, lambda m: m.group(2) * int(m.group(1)), sequence)
        return sequence

    def decode_sequence(self, sequence: str) -> list[str]:
        """Decode a sequence string into the motor-controller command list.

        Processing steps:

        1. Strip all whitespace.
        2. Expand ``N(…)`` repetition groups via :meth:`expand_parentheses`.
        3. Replace ``[N]`` bracket notation with a temporary ``<BNB>``
           placeholder to protect it from the general tokeniser.
        4. Tokenise into numbers-with-units, ``<BNB>`` placeholders, and ``T``.
        5. Convert time values to milliseconds using the unit multipliers.
        6. Build the final list prefixed with ``NbAcqu`` and
           ``TimeBetweenAcqu``.

        Supported time units and their millisecond multipliers:

        ======  ===========
        Unit    Multiplier
        ======  ===========
        ``ms``  1
        ``s``   1000
        ``us``  0.001
        ``µs``  0.001
        ``m``   1
        *(none)*  1
        ======  ===========

        Args:
            sequence: Human-readable sequence string, e.g.
                ``"2(100ms L 50ms T [3])"``

        Returns:
            A flat list of strings in the motor-controller format::

                [str(NbAcqu), '|', str(TimeBetweenAcqu), '|',
                 token, token, …]

            Where each token is one of:

            - ``"{value}"`` — a number converted to ms (e.g. ``"100.0"``).
            - ``"{char}"`` — a bare letter following a numeric token.
            - ``"{N}!"`` — a bracketed integer (from ``[N]``).
            - ``"T"`` — the literal trigger token.
        """
        sequence = sequence.replace(" ", "")

        sequence = self.expand_parentheses(sequence)

        sequence = re.sub(r'\[(\d+)\]', r'<B\1B>', sequence)

        token_pattern = re.compile(
            r'(\d+(?:\.\d+)?(?:ms|µs|us|s|m)?[A-Za-z]?)|(<B\d+B>)|(T)'
        )
        tokens = [t[0] or t[1] or t[2] for t in token_pattern.findall(sequence)]

        time_multipliers = {
            'ms': 1,
            's': 1000,
            'us': 0.001,
            'µs': 0.001,
            'm': 1,
            '': 1,
        }

        listFin = [str(self.NbAcqu), '|', str(self.TimeBetweenAcqu), '|']

        for token in tokens:
            if token.startswith('<B'):
                val = token[2:-2]
                listFin.append(f'{val}!')
                continue

            if token == 'T':
                listFin.append('T')
                continue

            match = re.match(r'(\d+(?:\.\d+)?)(ms|µs|us|s|m)?([A-Za-z]?)', token)
            if not match:
                continue

            num, unit, char = match.groups()
            multiplier = time_multipliers.get(unit, 1)
            value = float(num) * multiplier
            value_str = f'{value:.1f}' if '.' in str(value) or 'e' in str(value) else str(value)
            listFin.append(value_str)
            if char:
                listFin.append(char)

        return listFin