import re

class sequence_decoder:
    
    def __init__(self, mc=None, NbAcqu=1, TimeBetweenAcqu=0):
        self.mc = mc
        self.NbAcqu = NbAcqu
        self.TimeBetweenAcqu = TimeBetweenAcqu
    
    def expand_parentheses(self, sequence):
        # Keep expanding until no more patterns like 4(...) remain
        pattern = re.compile(r'(\d+)\(([^()]+)\)')
        while re.search(pattern, sequence):
            sequence = re.sub(pattern, lambda m: m.group(2) * int(m.group(1)), sequence)
        return sequence

    def decode_sequence(self, sequence):
        sequence = sequence.replace(" ", "")
        
        # Step 1: Expand parentheses
        sequence = self.expand_parentheses(sequence)
        
        # Step 2: Handle bracketed numbers
        sequence = re.sub(r'\[(\d+)\]', r'<B\1B>', sequence)
        
        # Step 3: Tokenize numbers with optional units and letters, and bracketed numbers
        token_pattern = re.compile(
            r'(\d+(?:\.\d+)?(?:ms|µs|us|s|m)?[A-Za-z]?)|(<B\d+B>)|(T)'
        )
        tokens = [t[0] or t[1] or t[2] for t in token_pattern.findall(sequence)]
        
        # Step 4: Time multipliers
        time_multipliers = {
            'ms': 1,
            's': 1000,
            'us': 0.001,
            'µs': 0.001,
            'm': 1,
            '': 1
        }
        
        # Step 5: Build final list
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
            # Remove .0 if integer-like
            value_str = f'{value:.1f}' if '.' in str(value) or 'e' in str(value) else str(value)
            listFin.append(value_str)
            if char:
                listFin.append(char)
        
        return listFin
