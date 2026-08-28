from base.data_exporter import DataExporter
import pandas as pd


class ParquetExporter(DataExporter):
    def export_data(self, data, filepath=None):
        df = pd.DataFrame(data)
        df.to_parquet(path=filepath, engine="pyarrow", compression="snappy")
