from base.data_exporter import DataExporter
import pandas as pd


class CSVExporter(DataExporter):
    def export_data(self, data, filepath):
        df = pd.read_json(data)
        df.to_csv(filepath, index=False)
