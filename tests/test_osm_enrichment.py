from scripts.enrich_district_osm import _geometry_covers, area_km2, build_query


def test_geojson_polygon_point_membership_and_area():
    geometry = {
        "type": "Polygon",
        "coordinates": [[
            [77.0, 10.0], [78.0, 10.0], [78.0, 11.0],
            [77.0, 11.0], [77.0, 10.0],
        ]],
    }
    assert _geometry_covers(geometry, 77.5, 10.5)
    assert not _geometry_covers(geometry, 78.5, 10.5)
    assert 10_000 < area_km2(geometry) < 13_000
    query, bbox = build_query(geometry)
    assert bbox == (10.0, 77.0, 11.0, 78.0)
    assert "highway" in query and "amenity" in query and "waterway" in query


def test_geojson_polygon_hole_is_excluded():
    geometry = {
        "type": "Polygon",
        "coordinates": [
            [[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]],
            [[1, 1], [3, 1], [3, 3], [1, 3], [1, 1]],
        ],
    }
    assert _geometry_covers(geometry, 0.5, 0.5)
    assert not _geometry_covers(geometry, 2.0, 2.0)


def test_geojson_multipolygon_point_membership():
    geometry = {
        "type": "MultiPolygon",
        "coordinates": [
            [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
            [[[3, 3], [4, 3], [4, 4], [3, 4], [3, 3]]],
        ],
    }
    assert _geometry_covers(geometry, 3.5, 3.5)
    assert not _geometry_covers(geometry, 2.0, 2.0)
