import numpy as np

from motronic_autotuner.core import winols
from motronic_autotuner.core.winols import TargetMap, parse_export


def line(name, x_name, x_unit, cols, rows, z, x, y):
    parts = ["desc", name, "folder", "eZweidim", "eViewText", "eBars", "eLoHi", x_name, x_unit]
    parts += ["0"] * 4  # fields 10..13
    parts += [str(cols), str(rows)]
    parts += ["pad"] * 10
    parts += [" ".join(f"{v:g}" for v in z), " ".join(f"{v:g}" for v in x), " ".join(f"{v:g}" for v in y)]
    return ";".join(parts)


def write(tmp_path, *lines):
    p = tmp_path / "export.csv"
    p.write_text("\n".join(lines) + "\n", encoding="latin-1")
    return p


def test_standard_load(tmp_path):
    z = np.arange(6, dtype=float)  # 2 rows x 3 cols
    path = write(tmp_path, line("KFLDRL", "Relativer Solladedruck", "hPa", 3, 2, z, [0, 50, 95], [1000, 2000]))
    r = parse_export(path, [TargetMap("KFLDRL", "rpm_boost", "kfldrl_x", "base_kfldrl", "Boost")])
    assert r.rows[0].status == winols.STATUS_LOADED and r.rows[0].dims == "2 x 3"
    np.testing.assert_array_equal(r.base_maps["base_kfldrl"], [[0, 1, 2], [3, 4, 5]])
    assert r.axes["kfldrl_x"].tolist() == [0, 50, 95]
    assert r.axes["rpm_boost"].tolist() == [1000, 2000]


def test_rpm_on_x_is_flipped(tmp_path):
    z = np.arange(6, dtype=float)  # 2 rows (load) x 3 cols (rpm) as WinOLS exported it
    path = write(tmp_path, line("KFZW_0", "Motordrehzahl", "U/min", 3, 2, z, [1000, 2000, 3000], [20, 80]))
    r = parse_export(path, [TargetMap("KFZW", "rpm_ign", "load_ign", "base_kfzw", "Ign")])
    assert r.rows[0].status == winols.STATUS_FLIPPED and r.rows[0].dims == "3 x 2"
    np.testing.assert_array_equal(r.base_maps["base_kfzw"], [[0, 3], [1, 4], [2, 5]])
    assert r.axes["rpm_ign"].tolist() == [1000, 2000, 3000]
    assert r.axes["load_ign"].tolist() == [20, 80]


def test_direct_keeps_export_orientation(tmp_path):
    z = np.arange(6, dtype=float)
    path = write(tmp_path, line("KFVPDKSD", "Motordrehzahl", "U/min", 3, 2, z, [1000, 2000, 3000], [1.5, 2.0]))
    r = parse_export(path, [TargetMap("KFVPDKSD", "pratio_kfvp", "rpm_kfvp", "base_kfvp", "H", direct=True)])
    assert r.rows[0].status == winols.STATUS_DIRECT
    assert r.base_maps["base_kfvp"].shape == (2, 3)
    assert r.axes["rpm_kfvp"].tolist() == [1000, 2000, 3000]
    assert r.axes["pratio_kfvp"].tolist() == [1.5, 2.0]


def test_size_heal_and_missing(tmp_path):
    z = np.arange(6, dtype=float)
    # declared 3 cols x 2 rows but the axes are the other way round
    path = write(tmp_path, line("FKKVS", "Einspritzzeit", "ms", 3, 2, z, [1, 2], [600, 1000, 2000]))
    r = parse_export(path, [
        TargetMap("FKKVS", "rpm_fuel", "te", "base_fkkvs", "Fuel"),
        TargetMap("KFURL", "rpm_url", "vvt_url", "base_kfurl", "SR"),
    ])
    assert r.rows[0].status == winols.STATUS_TRANSPOSED
    assert r.base_maps["base_fkkvs"].shape == (3, 2)
    assert r.rows[1].status == winols.STATUS_MISSING
    assert r.missing == ["KFURL"]
    assert r.loaded == 1


def test_single_row_map_gets_zero_y(tmp_path):
    path = write(tmp_path, line("KFFWL", "Motortemperatur", "Grad C", 4, 1, [1, 1, 1, 1], [-30, 0, 40, 80], []))
    r = parse_export(path, [TargetMap("KFFWL", "tmot", "kffwl_trim", "base_kffwl", "W")])
    assert r.rows[0].status == winols.STATUS_LOADED and r.rows[0].dims == "1 x 4"
    assert r.base_maps["base_kffwl"].shape == (1, 4)
    # as in MATLAB: x values go to the x key, the synthetic single y value to the y key
    assert r.axes["kffwl_trim"].tolist() == [-30.0, 0.0, 40.0, 80.0]
    assert r.axes["tmot"].tolist() == [0.0]
