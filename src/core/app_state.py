"Application state management for the JTS application."
"Centralized state management for the JTS application, including experiment data and device connections."
"This module defines the AppState class, which serves as a centralized container for the application's state. "
"It holds information about the current experiment sequence, configuration, and references to hardware instances."
"This allows different components of the application to access and modify shared state in a consistent way."


class AppState:
    def __init__(self):
        self.sequenced_dict = {}
        self.sequence_list = {}
        self.frequency_config = {}

        self.experiment_metadata = {}
        self.UUID_sequence_input_list = {}
        self.decoded_sequence_list = {}

        self.adc_instance = None
        self.esp32_instance = None
        self.acquisition_type = None  # "Sequence" or "Frequency"

        # List of dicts: {name, acquisition_type, operator, project, sample_id, date}
        self.experiments = []

        # Per-sequence parameters keyed by sequence n (stable unique int)
        self.sequence_parameters = {}

        # Global/default parameter config (fallback when no per-sequence params set)
        self.parameter_config = {
            "baseline_points":          0,
            "nbr_of_averages":          1,
            "time_between_averages_ms": 0,
            "nbr_sequences_ignored":    0,
            "time_before_next_seq_ms":  0,
        }

        self.total_time = None

    def set_total_time(self, total_time):
        self.total_time = total_time

    def get_total_time(self):
        return self.total_time

    def set_decoded_sequence_list(self, decoded_sequence, n):
        self.decoded_sequence_list[n] = decoded_sequence

    def get_decoded_sequence_list(self):
        return self.decoded_sequence_list

    def set_UUID_sequence_input(self, uuid, n):
        self.UUID_sequence_input_list[n] = uuid

    def get_UUID_sequence_input(self):
        return self.UUID_sequence_input_list

    def add_experiment(self, name: str, acquisition_type: str, experiment_type: str):
        self.experiments.append({
            "name": name,
            "acquisition_type": acquisition_type,
            "experiment_type": experiment_type,
            "operator": "", "project": "", "sample_id": "", "date": "", "comments": "",
        })

    def update_experiment_metadata(self, name: str, key: str, value: str):
        """Update a single metadata field for the experiment with the given name."""
        for exp in self.experiments:
            if exp["name"] == name:
                exp[key] = value
                return

    def get_experiments(self):
        return list(self.experiments)

    def set_experiment_type(self, experiment_type: str):
        self.experiment_type = experiment_type

    def get_experiment_type(self):
        return self.experiment_type

    def set_acquisition_type(self, acquisition_type: str):
        self.acquisition_type = acquisition_type

    def get_acquisition_type(self) -> str:
        return self.acquisition_type

    def set_adc_instance(self, adc_instance):
        self.adc_instance = adc_instance

    def get_adc_instance(self):
        return self.adc_instance

    def set_esp32_instance(self, esp32_instance):
        self.esp32_instance = esp32_instance

    def get_esp32_instance(self):
        return self.esp32_instance

    def set_sequence_list(self, sequence_list):
        """Store a list of dicts: {str_sequence, decoded, nbr_of_points}."""
        self.sequence_list = sequence_list

    def get_sequence_list(self):
        return self.sequence_list

    def set_parameter_list(self, n, params: dict):
        """Store parameter dict for sequence n."""
        self.sequence_parameters[n] = dict(params)

    def get_parameter_list(self, n) -> dict:
        """Return parameter dict for sequence n, falling back to global config."""
        return self.sequence_parameters.get(n)
