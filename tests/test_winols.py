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


HEADER64 = ";".join(
    ["Name", "IdName", "FolderName", "Type", "ViewMode", "RWin", "DataOrg", "bReciprocal", "bSigned", "bDelta",
     "bPercent", "bOriginal", "bOriginalValues", "Columns", "Rows"] + [f"f{i}" for i in range(15, 29)]
    + ["AxisX.Name", "AxisX.IdName", "AxisX.Unit"] + [f"x{i}" for i in range(32, 45)]
    + ["AxisY.Name", "AxisY.IdName", "AxisY.Unit"] + [f"y{i}" for i in range(48, 61)]
    + ["Fieldvalues.Values", "AxisX.Values", "AxisY.Values"])


def line64(name, cols, rows, z, x, y, x_name="", x_unit="", y_name="", y_unit="", map_type="eZweidim"):
    """A map line in the 64-field export layout of current WinOLS versions."""
    parts = ["desc", name, "folder", map_type, "eViewText", "eBars", "eLoHi"] + ["0"] * 6 + [str(cols), str(rows)]
    parts += ["0"] * 14 + [x_name, "", x_unit] + ["0"] * 13 + [y_name, "", y_unit] + ["0"] * 13
    parts += [" ".join(f"{v:g}" for v in z), " ".join(f"{v:g}" for v in x), " ".join(f"{v:g}" for v in y)]
    assert len(parts) == 64
    return ";".join(parts)


RPM10 = [700, 1000, 1520, 2000, 2520, 3000, 3520, 4000, 5000, 6000]
VVT6 = [0, 1, 2, 3, 20, 22]
URL = TargetMap("KFURL", "rpm_url", "vvt_url", "base_kfurl", "SR")


def test_new_layout_with_rpm_columns_is_flipped_to_rpm_rows(tmp_path):
    z = np.arange(60, dtype=float)                       # 6 rows (vvt) x 10 cols (rpm), as the 362287 export has it
    path = write(tmp_path, HEADER64, line64("KFURL", 10, 6, z, RPM10, VVT6, x_unit="U/min", y_unit="\xb0KW"))
    r = parse_export(path, [URL])
    assert r.rows[0].status == winols.STATUS_FLIPPED and r.rows[0].dims == "10 x 6"
    assert r.base_maps["base_kfurl"].shape == (10, 6)
    np.testing.assert_array_equal(r.base_maps["base_kfurl"][:, 2], z.reshape(6, 10)[2])
    assert r.axes["rpm_url"].tolist() == RPM10 and r.axes["vvt_url"].tolist() == VVT6


def test_square_map_with_rpm_columns_is_flipped_from_the_values_alone(tmp_path):
    z = np.arange(16, dtype=float)
    path = write(tmp_path, HEADER64, line64("KFPBRK", 4, 4, z, [1000, 2000, 3000, 4000], [50, 60, 70, 80]))
    r = parse_export(path, [TargetMap("KFPBRK", "rpm_pbrk", "load_pbrk", "base_kfpbrk", "SR")])
    assert r.rows[0].status == winols.STATUS_FLIPPED
    assert r.axes["rpm_pbrk"].tolist() == [1000, 2000, 3000, 4000] and r.axes["load_pbrk"].tolist() == [50, 60, 70, 80]
    np.testing.assert_array_equal(r.base_maps["base_kfpbrk"], z.reshape(4, 4).T)


def test_value_lists_swapped_against_the_axis_names_still_land_rpm_on_rows(tmp_path):
    # the 032HJ export: AxisX says Motordrehzahl but AxisX.Values holds the VVT list
    z = np.arange(60, dtype=float)
    path = write(tmp_path, HEADER64, line64("KFURL", 10, 6, z, VVT6, RPM10, x_name="Motordrehzahl", x_unit="U/min"))
    r = parse_export(path, [URL])
    assert r.rows[0].status == winols.STATUS_TRANSPOSED and r.rows[0].dims == "10 x 6"
    assert r.base_maps["base_kfurl"].shape == (10, 6)
    assert r.axes["rpm_url"].tolist() == RPM10 and r.axes["vvt_url"].tolist() == VVT6


def test_pressure_columns_with_rpm_rows_are_left_alone(tmp_path):
    z = np.arange(24, dtype=float)
    path = write(tmp_path, HEADER64, line64("KFLDIMX", 4, 6, z, [250, 500, 1000, 1400], VVT6[:0] + [1000, 1500, 2000, 2500, 3000, 3500],
                                            x_unit="hPa", y_unit="U/min"))
    r = parse_export(path, [TargetMap("KFLDIMX", "rpm_boost", "boost", "base_kfldimx", "B")])
    assert r.rows[0].status == winols.STATUS_LOADED and r.base_maps["base_kfldimx"].shape == (6, 4)


def test_direct_map_with_rpm_columns_is_flipped_too(tmp_path):
    # the 018J and 362287 exports have KFVPDKSD with rpm along the columns
    z = np.arange(6, dtype=float)
    path = write(tmp_path, HEADER64, line64("KFVPDKSD", 3, 2, z, [1000, 2000, 3000], [1.5, 2.0], x_unit="U/min"))
    r = parse_export(path, [TargetMap("KFVPDKSD", "rpm_kfvp", "pratio_kfvp", "base_kfvp", "H", direct=True)])
    assert r.rows[0].status == winols.STATUS_FLIPPED
    assert r.axes["rpm_kfvp"].tolist() == [1000, 2000, 3000] and r.axes["pratio_kfvp"].tolist() == [1.5, 2.0]
    assert r.base_maps["base_kfvp"].shape == (3, 2)


RATIO3 = [0.9, 1.0, 1.1]
RPM3 = [1000, 2000, 3000]
KFVP = TargetMap("KFVPDKSD", "rpm_kfvp", "pratio_kfvp", "base_kfvp", "H", direct=True)


def test_inverted_map_new_style_values_run_along_x_first(tmp_path):
    # 360288 / 362287 style: units match the lists, values stored [rpm][ratio]
    z = np.arange(9, dtype=float)
    path = write(tmp_path, HEADER64, line64("KFVPDKSD", 3, 3, z, RPM3, RATIO3, x_unit="U/min", y_unit="-",
                                            map_type="eZweiInv"))
    r = parse_export(path, [KFVP])
    assert r.rows[0].status == winols.STATUS_FLIPPED
    np.testing.assert_array_equal(r.base_maps["base_kfvp"], z.reshape(3, 3))        # rows rpm, cols ratio
    assert r.axes["rpm_kfvp"].tolist() == RPM3 and r.axes["pratio_kfvp"].tolist() == RATIO3


def test_inverted_map_old_style_values_run_along_y_first(tmp_path):
    # 032HJ / 018J style: the unit that says rpm sits on the other list, values stored [ratio][rpm]
    z = np.arange(9, dtype=float)
    path = write(tmp_path, HEADER64, line64("KFVPDKSD", 3, 3, z, RPM3, RATIO3, x_unit="-", y_unit="U/min",
                                            map_type="eZweiInv"))
    r = parse_export(path, [KFVP])
    assert r.rows[0].status == winols.STATUS_FLIPPED
    np.testing.assert_array_equal(r.base_maps["base_kfvp"], z.reshape(3, 3).T)
    assert r.axes["rpm_kfvp"].tolist() == RPM3


def test_inverted_non_square_maps_both_styles(tmp_path):
    z = np.arange(8, dtype=float)
    rpm4, pct2 = [1000, 2000, 3000, 4000], [50, 95]
    new = line64("KFLDRL", 2, 4, z, rpm4, pct2, x_unit="U/min", y_unit="%", map_type="eZweiInv")       # [rpm][%]
    old = line64("KFPRG", 4, 2, z, [0, 22], rpm4, x_unit="U/min", y_unit="\xb0KW", map_type="eZweiInv")  # lists per definition
    path = write(tmp_path, HEADER64, new, old)
    r = parse_export(path, [TargetMap("KFLDRL", "rpm_boost", "kfldrl_x", "base_kfldrl", "B"),
                            TargetMap("KFPRG", "rpm_prg", "vvt_prg", "base_kfprg", "SR")])
    assert r.rows[0].status == winols.STATUS_FLIPPED and r.base_maps["base_kfldrl"].shape == (4, 2)
    np.testing.assert_array_equal(r.base_maps["base_kfldrl"], z.reshape(4, 2))
    assert r.axes["rpm_boost"].tolist() == rpm4 and r.axes["kfldrl_x"].tolist() == pct2
    assert r.rows[1].status == winols.STATUS_TRANSPOSED and r.base_maps["base_kfprg"].shape == (4, 2)
    np.testing.assert_array_equal(r.base_maps["base_kfprg"], z.reshape(4, 2))
    assert r.axes["rpm_prg"].tolist() == rpm4 and r.axes["vvt_prg"].tolist() == [0, 22]


def test_value_count_must_match_the_axes(tmp_path):
    path = write(tmp_path, HEADER64, line64("KFZW", 3, 2, np.arange(5, dtype=float), [10, 50, 90], [1000, 2000]))
    r = parse_export(path, [TargetMap("KFZW", "rpm_ign", "load_ign", "base_kfzw", "I")])
    assert r.rows[0].status == winols.STATUS_MISMATCH
