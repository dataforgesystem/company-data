from base.data_exporter import DataExporter
import json


class JSONExporter(DataExporter):
    def export_data(self, data, filepath=None):
        return json.dump(data, fp=filepath)
