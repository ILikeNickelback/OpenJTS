from sequence_builders.decoder import sequence_decoder


class sequence_control:
    def __init__(self):
        pass

    def save_sequence(self):
        pass

    def load_sequence(self):
        pass

    def check_sequence(self, sequence):
        pass

    def count_nbr_of_points(self, sequence):
        nbr_of_points = sequence.count('D')
        return nbr_of_points

    def decode_sequence(self, sequence):
        decoder = sequence_decoder()
        self.check_sequence(sequence)
        decoded_sequence = decoder.decode_sequence(sequence)
        nbr_of_points = self.count_nbr_of_points(decoded_sequence)
        return decoded_sequence, nbr_of_points
