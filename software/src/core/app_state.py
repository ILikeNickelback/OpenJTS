#TODO: Consider using prorperty decorators for getters and setters in AppState class to improve encapsulation and maintainability.

class AppState:
    """Shared application state container for the JTS data acquisition system.

    Holds all runtime state including hardware instances, experiment metadata,
    sequence data, and acquisition parameters. Acts as a central store passed
    between UI and hardware layers.
    """
    def __init__(self):
        self.sequenced_dict = {}
        self.sequence_list = {}
        self.frequency_config = {}
        self.experiment_type = None 

        self.experiment_metadata = {}
        self.UUID_sequence_input_list = {}
        self.decoded_sequence_list = {}

        self.adc_instance = None
        self.esp32_instance = None
        self._acquisition_type = None

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

    def set_total_time(self, total_time: float) -> None:
        """Set the estimated total acquisition time.

        Args:
            total_time: Total time in milliseconds for the current acquisition run.
        """
        self.total_time = total_time

    def get_total_time(self) -> float | None:
        """Return the estimated total acquisition time.

        Returns:
            Total time in milliseconds, or None if not yet set.
        """
        return self.total_time

    def set_decoded_sequence_list(self, decoded_sequence, n: int) -> None:
        """Store the decoded sequence for sequence index n.

        Args:
            decoded_sequence: Decoded representation of the sequence (e.g. list of pulses).
            n: Stable unique integer index identifying the sequence.
        """
        self.decoded_sequence_list[n] = decoded_sequence

    def get_decoded_sequence_list(self) -> dict:
        """Return all decoded sequences keyed by sequence index.

        Returns:
            Dict mapping sequence index (int) to its decoded sequence.
        """
        return self.decoded_sequence_list

    def set_UUID_sequence_input(self, uuid, n: int) -> None:
        """Store the UUID of the sequence input widget for sequence index n.

        Args:
            uuid: Unique identifier for the sequence input (string or UUID object).
            n: Stable unique integer index identifying the sequence.
        """
        self.UUID_sequence_input_list[n] = uuid

    def get_UUID_sequence_input(self) -> dict:
        """Return all sequence input UUIDs keyed by sequence index.

        Returns:
            Dict mapping sequence index (int) to its input UUID.
        """
        return self.UUID_sequence_input_list

    def add_experiment(self, name: str, acquisition_type: str, experiment_type: str) -> None:
        """Append a new experiment entry to the experiment list.

        Args:
            name: Display name for the experiment.
            acquisition_type: Acquisition mode, either ``"Sequence"`` or ``"Frequency"``.
            experiment_type: Category or protocol type of the experiment.
        """
        self.experiments.append({
            "name": name,
            "acquisition_type": acquisition_type,
            "experiment_type": experiment_type,
            "operator": "", "project": "", "sample_id": "", "date": "", "comments": "",
        })

    def update_experiment_metadata(self, name: str, key: str, value: str) -> None:
        """Update a single metadata field for the experiment with the given name.

        Args:
            name: Name of the experiment to update.
            key: Metadata field to update (e.g. ``"operator"``, ``"project"``).
            value: New value for the field.
        """
        for exp in self.experiments:
            if exp["name"] == name:
                exp[key] = value
                return

    def get_experiments(self) -> list[dict]:
        """Return a shallow copy of the experiment list.

        Returns:
            List of experiment dicts, each containing name, acquisition_type,
            experiment_type, operator, project, sample_id, date, and comments.
        """
        return list(self.experiments)

    def set_experiment_type(self, experiment_type: str) -> None:
        """Set the current experiment type.

        Args:
            experiment_type: Category or protocol type of the experiment.
        """
        self.experiment_type = experiment_type

    def get_experiment_type(self) -> str:
        """Return the current experiment type.

        Returns:
            Category or protocol type of the experiment.
        """
        return self.experiment_type

    @property
    def acquisition_type(self) -> str | None:
        """Acquisition mode: ``"Sequence"`` or ``"Frequency"``, or None if not set."""
        return self._acquisition_type

    @acquisition_type.setter
    def acquisition_type(self, value: str) -> None:
        if value not in {"Sequence", "Frequency"}:
            raise ValueError(f"acquisition_type must be 'Sequence' or 'Frequency', got {value!r}")
        self._acquisition_type = value

    def set_adc_instance(self, adc_instance) -> None:
        """Store a reference to the ADC hardware instance.

        Args:
            adc_instance: Initialized ADC driver/controller object.
        """
        self.adc_instance = adc_instance

    def get_adc_instance(self):
        """Return the stored ADC hardware instance.

        Returns:
            The ADC driver/controller object, or None if not set.
        """
        return self.adc_instance

    def set_esp32_instance(self, esp32_instance) -> None:
        """Store a reference to the ESP32 hardware instance.

        Args:
            esp32_instance: Initialized ESP32 communication object.
        """
        self.esp32_instance = esp32_instance

    def get_esp32_instance(self):
        """Return the stored ESP32 hardware instance.

        Returns:
            The ESP32 communication object, or None if not set.
        """
        return self.esp32_instance

    def set_sequence_list(self, sequence_list: dict) -> None:
        """Store the full sequence list.

        Args:
            sequence_list: Dict of sequence entries, each containing
                ``str_sequence``, ``decoded``, and ``nbr_of_points``.
        """
        self.sequence_list = sequence_list

    def get_sequence_list(self) -> dict:
        """Return the full sequence list.

        Returns:
            Dict of sequence entries keyed by sequence index.
        """
        return self.sequence_list

    def set_parameter_list(self, n: int, params: dict) -> None:
        """Store the parameter dict for sequence n.

        Args:
            n: Stable unique integer index identifying the sequence.
            params: Dict of acquisition parameters for the sequence.
        """
        self.sequence_parameters[n] = dict(params)

    def get_parameter_list(self, n: int) -> dict | None:
        """Return the parameter dict for sequence n, or None if not set.

        Falls back to None when no per-sequence parameters have been stored;
        callers should use ``parameter_config`` as the global fallback.

        Args:
            n: Stable unique integer index identifying the sequence.

        Returns:
            Parameter dict for sequence n, or None if absent.
        """
        return self.sequence_parameters.get(n)
