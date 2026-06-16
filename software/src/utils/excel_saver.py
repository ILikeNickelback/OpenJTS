import csv
from datetime import datetime
from dearpygui.dearpygui import *

class CSVDataSaver:
    def __init__(self):
        self.filename = None
        self.data_ready = False
        self.x_array = []
        self.y_array = []

    def save_data(self, x_array, y_array):
        if len(x_array) != len(y_array):
            raise ValueError("x_array and y_array must be the same length.")
        
        self.x_array = x_array
        self.y_array = y_array
        self.data_ready = True
        self.show_save_dialog()

    def show_save_dialog(self):
        with file_dialog(directory_selector=False, show=True, callback=self.save_to_file, width=500, height=300, modal=True):
            add_file_extension(".csv", color=(0, 255, 0, 255))

    def save_to_file(self, sender, app_data):
        self.filename = app_data['file_path_name']
        if self.filename and self.data_ready:
            with open(self.filename, 'w', newline='') as csvfile:
                csv_writer = csv.writer(csvfile)
                csv_writer.writerow(['time', 'data'])
                for x, y in zip(self.x_array, self.y_array):
                    csv_writer.writerow([x, y])
            print(f"Data saved to {self.filename}")
            self.data_ready = False