
from config.config import config

def calculate_nbr_of_points(frequencyconfig):
    normal_pulses_period = config["Frequency"].get("normal_pulses_per_period")
    overide_pulses_period = config["Frequency"].get("override_pulses_per_period")
    sampling_rate = config["Frequency"].get("sampling_rate")
    
    saturating_pulse_data = frequencyconfig["saturating_pulse_data"]
    
     
    total_nbr_of_points = (frequencyconfig["nbr_of_periods"] * normal_pulses_period)
    print(total_nbr_of_points)

    return total_nbr_of_points    