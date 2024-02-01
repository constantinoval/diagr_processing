import os

import dearpygui.dearpygui as dpg
from libs.diagramm_lib import Diagramm
import json
import sys
from glob import glob
from libs.dpgfiledialog import dpgDirFileDialog
from dataclasses import dataclass
from libs.odbc_access_lib import expODBC

@dataclass
class ExperimentTableRow:
    code: str
    diag: Diagramm
    line_series_full_diag: int
    line_series_plastic_diag: int
    group: int = -1


experiments: dict[str, ExperimentTableRow] = {}

# if len(sys.argv) >= 2:
#     xls_path = sys.argv[1]
# else:
#     xls_path = './с714.xls'
# xls_data = pd.read_excel(xls_path, usecols=[0], names=['exp_code'])
diagramm = Diagramm()
db_path: str = ""
exp_db: expODBC | None = None
current_experimtnt_code: str = ""
working_dir = os.path.curdir
EXP_TYPE_CODES = {
    "Растяжение": "t",
    "Сжатие": "c",
}

dpg.create_context()
dpg.create_viewport(height=900, title='Elastic modulus correction')
dpg.setup_dearpygui()

# with dpg.theme() as choosen_button:
#     with dpg.theme_component(dpg.mvButton):
#         dpg.add_theme_color(dpg.mvThemeCol_Button, (91, 164, 169))

with dpg.theme() as global_theme:
    with dpg.theme_component(dpg.mvMenuItem):
        dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, y=10)
    with dpg.theme_component(dpg.mvLineSeries):
        dpg.add_theme_style(dpg.mvPlotStyleVar_LineWeight, 2, category=dpg.mvThemeCat_Plots)
#
dpg.bind_theme(global_theme)

with dpg.font_registry():
    with dpg.font("c:/Windows/Fonts/arial.ttf", 16, default_font=True) as default_font:
        dpg.add_font_range_hint(dpg.mvFontRangeHint_Cyrillic)
        dpg.bind_font(default_font)


def load_db(file_path, update_working_dir = True):
    if file_path is None:
        return
    global db_path
    global exp_db
    global working_dir
    if os.path.exists(file_path):
        db_path = file_path
        exp_db = expODBC(file_path)
        mat_codes = [str(m['КодМатериала']) for m in exp_db.getMaterials()]
        dpg.configure_item(
            mat_codes_cb,
            items=mat_codes,
            default_value="",
        )
        dpg.configure_item(
            exp_codes_cb,
            items=[],
            default_value="",
        )
        if update_working_dir:
            working_dir = os.path.abspath(os.curdir)


def choose_db_file_file(sender, app_data, user_data):
    fd = dpgDirFileDialog(
        extensions=['accdb'],
        callback=load_db,
    )
    fd.show()

def update_codes_cb(sender, app_data, user_data):
    exp_type = EXP_TYPE_CODES[dpg.get_value(exp_type_codes_cb)]
    mat_num = dpg.get_value(mat_codes_cb)
    numbers = [n['НомерОбразца'] for n in exp_db.getNumbers(exp_type, mat_num)]
    dpg.configure_item(
        exp_codes_cb,
        items=[f"{exp_type}{mat_num}-{n}" for n in numbers],
    )
    if dpg.get_value(exp_type_codes_cb) != 'Растяжение':
        dpg.set_value(mlr_cb, False)
        dpg.configure_item(eN, show=False)
        diagramm._MLR_correction = False
    dpg.configure_item(
        MLR_group,
        show=dpg.get_value(exp_type_codes_cb) == 'Растяжение',
    )


def choose_experiment(sender, app_data, user_data):
    global diagramm
    if exp_db is None:
        return
    dpg.set_value(ds_slider, 0.0)
    if os.path.exists(json_path:=(os.path.join(working_dir, app_data)+'.json')):
        diagramm.load_from_json(json_path)
        dpg.set_value(ep1, diagramm.ep1)
        dpg.set_value(ep2, diagramm.ep2)
        dpg.set_value(eN, max(diagramm.eN, 0))
        dpg.set_value(exp_type_codes_cb, {'t': 'Растяжение', 'c': 'Сжатие'}[diagramm.etype])
        dpg.set_value(mlr_cb, diagramm._MLR_correction)
        dpg.configure_item(MLR_group, show=diagramm.etype=='t')
        dpg.configure_item(eN, show=diagramm._MLR_correction)
        dpg.set_value(elastic_multiplier, diagramm._E_multiplier)
        dpg.set_value(delta_e, diagramm._delta_e)
        dpg.set_value(ds_slider, diagramm.ds)
        apply_markers(None, None, None)
    else:
        diagramm.load_from_db(exp_db, app_data)
        diagramm.ep1 = dpg.get_value(ep1)
        diagramm.ep2 = dpg.get_value(ep2)
        diagramm._E_multiplier = dpg.get_value(elastic_multiplier)
        diagramm._delta_e = dpg.get_value(delta_e)
        diagramm._MLR_correction = dpg.get_value(mlr_cb) and (dpg.get_value(exp_codes_cb)=='Растяжение')
        dpg.set_value(corrected_diag, [[], []])
        dpg.set_value(plastic_diag_eng, [[], []])
        dpg.set_value(plastic_diag_true, [[], []])
    update_E(None, dpg.get_value(etalon_e), None)
    dpg.set_value(
        diag,
        [
            list(diagramm._e),
            list(diagramm._s),
        ]
    )
    dpg.fit_axis_data(x1)
    dpg.fit_axis_data(y1)


def apply_markers(seder, app_data, user_data):
    ep1_value = dpg.get_value(ep1)
    ep2_value = dpg.get_value(ep2)
    if ep1_value == ep2_value:
        return
    if ep1_value > ep2_value:
        ep1_value, ep2_value = ep2_value, ep1_value
    diagramm.ep1 = ep1_value
    diagramm.ep2 = ep2_value
    correct_elastic(None, dpg.get_value(elastic_multiplier), None)
    if diagramm._MLR_correction:
        diagramm.eN = dpg.get_value(eN)
    dpg.set_value(
        plastic_diag_eng,
        [
            list(diagramm.ep_eng),
            list(diagramm.sp_eng),
        ]
    )
    dpg.set_value(
        plastic_diag_true,
        [
            list(diagramm.ep_true),
            list(diagramm.sp_true),
        ]
    )
    dpg.fit_axis_data(x2)
    dpg.fit_axis_data(y2)


def update_E(sender, app_data, user_data):
    if len(diagramm._e) == 0:
        return
    smax = diagramm._s.max()
    emax = smax / app_data
    dpg.set_value(
        e_line,
        [[0, emax], [0, smax]]
    )


def correct_elastic(sender, app_data, user_data):
    diagramm._E_multiplier = app_data
    dpg.set_value(
        corrected_diag,
        [
            list(diagramm.e),
            list(diagramm.s),
        ]
    )


def shift_curves(sendedr, app_data, user_data):
    diagramm._delta_e = app_data
    dpg.set_value(
        corrected_diag,
        [
            list(diagramm.e),
            list(diagramm.s),
        ]
    )
    dpg.fit_axis_data(x1)


def stress_level_callback(sender, app_data, user_data):
    sl = dpg.get_value(stress_level_line)
    dpg.set_value(stress_level_text, f'{sl: g}')


def save_callback(sender, app_data, user_data):
    if not diagramm.exp_code:
        return
    json.dump(
        diagramm.as_dict,
        open(
            os.path.join(
                working_dir,
                f'{diagramm.exp_code}.json'
            ),
            'w')
    )


def show_hide_diagramm(sender: int, app_data: bool, user_data: ExperimentTableRow):
    dpg.configure_item(user_data.line_series_full_diag, show=app_data)
    dpg.configure_item(user_data.line_series_plastic_diag, show=app_data)


def update_group_plot(sender, app_data, user_data):
    global experiments
    # dpg.delete_item(yg1, children_only=True)
    # dpg.delete_item(yg2, children_only=True)
    # dpg.delete_item(yg3, children_only=True)
    for f in glob(os.path.join(working_dir, '*.json')):
        exp_code = os.path.basename(f)[:-5]
        dgr = Diagramm()
        dgr.load_from_json(f)
        if exp_code in experiments:
            exp = experiments[exp_code]
            exp.diag = dgr
            dpg.set_value(
                exp.line_series_full_diag,
                [dgr.e.tolist(), dgr.s.tolist()]
                )
            dpg.set_value(
                exp.line_series_plastic_diag,
                [dgr.ep_true.tolist(), dgr.sp_true.tolist()]
                )
        else:
            fd = dpg.add_line_series(dgr.e.tolist(), dgr.s.tolist(), label=dgr.exp_code, parent=yg1)
            pd = dpg.add_line_series(dgr.ep_true.tolist(), dgr.sp_true.tolist(), label=dgr.exp_code, parent=yg2)
            experiments[exp_code] = ExperimentTableRow(code=exp_code, diag=dgr,
                                                    line_series_full_diag=fd, line_series_plastic_diag=pd)
            with dpg.table_row(parent=experiments_table):
                dpg.add_text(exp_code)
                dpg.add_text(f'{dgr.T}')
                dpg.add_text(f'{dgr.mean_de_true:.0f}')
                dpg.add_checkbox(default_value=True, user_data=experiments[exp_code],
                                callback=show_hide_diagramm)
        # dpg.add_line_series(dgr.ep_true.tolist(), dgr.sp_true.tolist(), label=dgr.exp_code, parent=yg3)
    if dpg.get_value(autoscale_diags):
        dpg.fit_axis_data(xg1)
        dpg.fit_axis_data(yg1)
        dpg.fit_axis_data(xg2)
        dpg.fit_axis_data(yg2)
        # dpg.fit_axis_data(xg3)
        # dpg.fit_axis_data(yg3)



def set_working_dir(dir_path):
    if dir_path is None:
        return
    global working_dir
    working_dir = dir_path


def set_working_dir_callback(sender, app_data, user_data):
    fd = dpgDirFileDialog(
        current_path=working_dir,
        dir_mode=True,
        callback=set_working_dir,
    )
    fd.show()


def change_ds_callback(sender, app_data, user_data):
    global diagramm
    if diagramm is None:
        return
    diagramm.ds = app_data
    dpg.set_value(
        corrected_diag,
        [
            list(diagramm.e),
            list(diagramm.s),
        ]
    )


def clear_group_plot(sender, app_data, user_data):
    global experiments
    dpg.delete_item(yg1, children_only=True)
    dpg.delete_item(yg2, children_only=True)
    for row in dpg.get_item_children(experiments_table)[1]:
        dpg.delete_item(row)  
    experiments = {}    


def MLR_correction_callback(sender, app_data, user_data):
    diagramm._MLR_correction = app_data
    dpg.configure_item(eN, show=app_data)

with dpg.window(label="Correct module", width=800, height=700, tag='main'):
    with dpg.menu_bar():
        with dpg.menu(label='Инструменты'):
            dpg.add_menu_item(label='Выбрать файл базы данных', callback=choose_db_file_file)
            dpg.add_menu_item(label='Установить рабочую директорию', callback=set_working_dir_callback)
            dpg.add_separator()
            dpg.add_menu_item(label='Выход', callback=dpg.stop_dearpygui)
        dpg.add_spacer(width=20)
        dpg.add_text('Код материала:')
        mat_codes_cb = dpg.add_combo(
            items=[],  # xls_data.exp_code.to_list(),
            callback=update_codes_cb,
            width=100,
        )
        dpg.add_text('Тип испытания:')
        exp_type_codes_cb = dpg.add_combo(
            items=['Сжатие', "Растяжение"],  # xls_data.exp_code.to_list(),
            callback=update_codes_cb,
            width=110,
            default_value='Сжатие'
        )
        dpg.add_text('Код испытания: ')
        exp_codes_cb = dpg.add_combo(
            items=[],  # xls_data.exp_code.to_list(),
            callback=choose_experiment,
            width=200,
        )
        dpg.add_text('Уровень напряжения: ')
        stress_level_text = dpg.add_text('')

    with dpg.group(horizontal=True):
        ds_slider = dpg.add_slider_float(vertical=True, width=10, format='', height=400, min_value=-100, max_value=100,
                                         callback=change_ds_callback)
        dpg.add_spacer(width=5)
        with dpg.subplots(1, 2, width=-1, height=400):
            with dpg.plot():
                x1 = dpg.add_plot_axis(dpg.mvXAxis, label='strain')
                y1 = dpg.add_plot_axis(dpg.mvYAxis, label='stress, MPa')
                diag = dpg.add_line_series(
                    x=[],
                    y=[],
                    parent=y1
                )
                corrected_diag = dpg.add_line_series(
                    x=[],
                    y=[],
                    parent=y1
                )
                e_line = dpg.add_line_series(
                    [],
                    [],
                    parent=y1
                )
                ep1 = dpg.add_drag_line(label='ep1', color=(255, 0, 0), show_label=False,
                                        callback=apply_markers)
                ep2 = dpg.add_drag_line(label='ep2', color=(0, 255, 0), show_label=False,
                                        callback=apply_markers)
                eN = dpg.add_drag_line(label='eN', color=(0, 0, 255), show_label=False,
                                        callback=apply_markers, show=False)
                stress_level_line = dpg.add_drag_line(
                    label='stress level', color=(255, 255, 255),
                    vertical=False, default_value=200,
                    show_label=False, callback=stress_level_callback
                )
            with dpg.plot():
                x2 = dpg.add_plot_axis(dpg.mvXAxis, label='strain')
                y2 = dpg.add_plot_axis(dpg.mvYAxis, label='stress, MPa')
                plastic_diag_eng = dpg.add_line_series([], [], parent=y2, label='eng')
                plastic_diag_true = dpg.add_line_series([], [], parent=y2, label='true')
                dpg.add_plot_legend()
    with dpg.table(header_row=True):
        dpg.add_table_column(init_width_or_weight=0.2, label='Модуль - эталон')
        dpg.add_table_column(init_width_or_weight=0.4, label='Коррекция модуля')
        dpg.add_table_column(init_width_or_weight=0.4, label='Сдвиг диаграммы')
        with dpg.table_row():
            etalon_e = dpg.add_drag_float(
                # label='E_etalon',
                min_value=10,
                max_value=200000,
                default_value=50000,
                speed=100,
                callback=update_E,
                clamped=True,
                width=-1,
            )
            with dpg.tooltip(dpg.last_item()):
                dpg.add_text('Модуль упругости')

            elastic_multiplier = dpg.add_drag_float(
                # label='correct_E',
                min_value=0.001,
                max_value=2,
                default_value=1,
                speed=0.01,
                callback=correct_elastic,
                clamped=True,
                width=-1,
            )
            with dpg.tooltip(dpg.last_item()):
                dpg.add_text('Наклон упругого участка')
            delta_e = dpg.add_drag_float(
                # label='shift',
                min_value=-0.05,
                max_value=0.05,
                default_value=0,
                speed=0.0001,
                callback=shift_curves,
                clamped=True,
                width=-1,
            )
            with dpg.tooltip(dpg.last_item()):
                dpg.add_text('Сдвиг диаграммы')
    with dpg.child_window(height=40, show=False) as MLR_group:
        with dpg.group(horizontal=True):
            mlr_cb = dpg.add_checkbox(label='MLR correction', default_value=False,
                             callback=MLR_correction_callback)
    with dpg.group(horizontal=True):
        dpg.add_button(label='Сохранить', width=90, height=30, callback=save_callback)
        dpg.add_button(label='Обновить групповую диаграмму', width=230, height=30, callback=update_group_plot)
        dpg.add_button(label='Очитстить групповую диаграмму', width=230, height=30, callback=clear_group_plot)
    with dpg.group(horizontal=True):
        with dpg.subplots(1, 2, width=-400, height=-20):
            with dpg.plot():
                xg1 = dpg.add_plot_axis(dpg.mvXAxis, label='strain')
                yg1 = dpg.add_plot_axis(dpg.mvYAxis, label='stress')
                dpg.add_plot_legend(outside=True)
            with dpg.plot():
                xg2 = dpg.add_plot_axis(dpg.mvXAxis, label='ep true')
                yg2 = dpg.add_plot_axis(dpg.mvYAxis, label='stress true')
        with dpg.table(scrollY=True, height=300) as experiments_table:
            dpg.add_table_column(label='Код')
            dpg.add_table_column(label='темпер.')
            dpg.add_table_column(label='скор. деф.')
            dpg.add_table_column(label='отобр.')
    autoscale_diags = dpg.add_checkbox(label='Автомасштабирование', default_value=True)

# dpg.show_style_editor()

dpg.show_viewport()
dpg.set_primary_window('main', True)
dpg.start_dearpygui()
dpg.destroy_context()
