import geopandas as gpd
from array import array
from shapely import LineString

og_flyover = gpd.read_file(r"\\file\Usersl$\lpa87\Home\Desktop\today\dense_smooth_14_11_25.geojson")
print(og_flyover)

points_txyz = []
z = 200.0
i = 0
line_string = og_flyover.geometry[0]

for i, (x, y, _z) in enumerate(line_string.coords):
    t = float(i)
    point = [t, x, y, z]
    points_txyz.append(point)


flattened_list = [item for sub_list in points_txyz for item in sub_list]
print(flattened_list)
