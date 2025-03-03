import dash
from dash import html, dcc, callback, Output, Input, State, ctx, ALL, Dash, dash_table, exceptions
from dash_extensions.enrich import DashProxy, MultiplexerTransform
from dash_iconify import DashIconify
import dash_mantine_components as dmc

import pandas as pd
import datetime
from datetime import datetime, timedelta
import ujson as json
import numpy as np
import ast
import re
import base64

import multiprocessing
from functools import partial

from modules.data import read_last_query_time, write_last_query_time, should_query_api, get_sat_data
from modules.propagation import propagate,spherical_to_cartesian, to_julian
from modules.observability import get_observable_objects
from modules.coord_frames import get_coord_sys
from modules.layout import layout

from astropy import units as u
from astropy.coordinates import get_sun, GCRS, TEME

from poliastro.bodies import Earth
from poliastro.twobody import Orbit
from astropy.time import Time
from poliastro.util import time_range
from poliastro.earth.plotting.utils import EARTH_PALETTE


#------------------------GLOBAL VARIABLES--------------------------------
color_palette=EARTH_PALETTE
PAGE_SIZE = 10
ITEMS_PER_PAGE = 7
propagated_data_store = {}
observations = []
summary_data = []
df = []

#-------------------------DATA BASE LOADING-------------------------------

LAST_QUERY_FILE = "database/last_query_time.json"
last_query_time = read_last_query_time(LAST_QUERY_FILE)
if should_query_api(last_query_time):
    get_sat_data()
    df = pd.read_json("database/updated_all_sat.json")
    write_last_query_time(LAST_QUERY_FILE, datetime.now())
else:
    df = pd.read_json("database/updated_all_sat.json")



#-------------------------APP INITIALIZATION------------------------------
external_stylesheets = [dmc.theme.DEFAULT_COLORS]
app = Dash(__name__, external_stylesheets=external_stylesheets)
app = DashProxy(transforms=[MultiplexerTransform()])
with open('templates/index.html', 'r') as file:
    app.index_string = file.read()

app.layout = layout



#-------------------------CALLBACK SECTION----------------------------------
@app.callback(
    Output('date_input', 'disabled'),
    Output('start_date_storage', 'data'),
    Input('initial_epoch_selection_group', 'value'),
    Input('date_input', 'value'),
)
def update_date_input(initial_epoch_selection_group, date_input_value):
    if initial_epoch_selection_group == 'Select time':
        start_date_var = date_input_value
        return False, start_date_var
    else:
        start_date_var = str(Time(Time.now(), scale="utc", format="datetime"))
        return True, start_date_var


@app.callback(
    Output("modal-objects", "opened"),
    Output("modal_created_objects", "opened"),
    Output("modal_propagation", "opened"),
    Output("modal-upload", "opened"),
    Input("propagate_button", "n_clicks"),
    Input("propagate_propagate_button", "n_clicks"),
    Input("more_objects_button", "n_clicks"),

    Input("create_objects_button", "n_clicks"),
    Input('creation_edition_output', 'data'),
    Input("modal_created_objects", "opened"),
    Input("modal_propagation", "opened"),
    Input("upload_new_objects", "n_clicks"),
    Input("upload-output", "children"),
    Input("modal-upload", "opened"),  
    Input('save_edited_created_button', 'n_clicks'),
    State("modal-objects", "opened"),
    State("modal_created_objects", "opened"),
    State("modal_propagation", "opened"),
    State("modal-upload", "opened"),
    prevent_initial_call=True
)
def toggle_modals(propagate_button, propagate_propagate_button, more_objects_button_clicks, 
                  create_objects_button_clicks, creation_edition_output, modal_created_objects_opened, 
                  modal_propagation_opened, upload_new_objects_clicks, upload_output, 
                  modal_upload_opened, save_edited_created_button, modal_objects_opened_state, 
                  modal_created_objects_opened_state, modal_propagation_opened_state, 
                  modal_upload_opened_state):
    
    triggered_id = ctx.triggered_id

    if triggered_id == "more_objects_button":
        return not modal_objects_opened_state, False, False, False
    elif triggered_id == "create_objects_button":
        return False, not modal_created_objects_opened_state, False, False
    elif triggered_id == "propagate_button":
        return False, False, not modal_propagation_opened_state, False
    elif triggered_id == "save_edited_created_button":
        if creation_edition_output == True:
            return True, False, False, False
        elif creation_edition_output == False:
            return False, True, False, False
    elif triggered_id == "propagate_propagate_button":
        return False, False, False, False
    elif triggered_id == "modal_created_objects" and not modal_created_objects_opened:
        return True, False, False, False
    elif triggered_id == "modal_propagation" and not modal_propagation_opened:
        return True, False, False, False
    elif triggered_id == "upload_new_objects":
        return False, False, False, not modal_upload_opened_state
    elif triggered_id == 'upload-output':
        if upload_output == "Successfully uploaded":
            return True, False, False, False 
        else:
            return False, False, False, True
    elif triggered_id == "modal-upload":
        if not modal_upload_opened: 
            return True, False, False, False  
        else:
            return False, False, False, True

    return (modal_objects_opened_state, modal_created_objects_opened_state, 
            modal_propagation_opened_state, modal_upload_opened_state)
    


@app.callback(
    Output('filters_store', 'data'),
    Input('save_filter_button', 'n_clicks'),
    State('variable_filter', 'value'),
    State('operation_filter', 'value'),
    State('quantity_filter', 'value'),
    State('filters_store', 'data'),
)
def save_filter(n_clicks, variable, operation, quantity, filters_store):
    if n_clicks is None:
        raise exceptions.PreventUpdate

    if not filters_store:
        last_item_id_in_filters_store = 0
    else:
        last_item_in_filters_store = filters_store[-1]
        last_item_id_in_filters_store = last_item_in_filters_store["filter_id"]

    new_filter = {
        "filter_id": int(last_item_id_in_filters_store) + 1,
        "variable": variable,
        "operation": operation,
        "quantity": quantity
    }

    filters_store.append(new_filter)

    return filters_store



@app.callback(
    Output('filters_badge','children'),
    Input('filters_store', 'data'),
)
def update_filters_badges (filters_store):
    return (
        dmc.Grid(
            [   
                html.Div(
                    [                
                        dmc.Text(
                            f"{item['variable']} {item['operation']} {item['quantity']}", 
                            size="xs",
                        ),
                        dmc.Button(
                            DashIconify(icon="mdi:cancel-bold", color="gray"),
                            id={'type': 'delete-button_filter', 'index_ID': item["filter_id"]},
                            variant="subtle",
                            size="compact-xs",
                            color="gray",
                            px=0, 
                            m=0, 
                            style={'margin-left': '5px',},
                        ),
                    ],
                    style={
                        'display': 'flex',
                        'align-items': 'center',
                        'margin-right': '10px',
                        'margin-top': '3px',
                        'background-color': '#f0f0f0', 
                        'padding': '0px 0px 0px 5px',  
                        'border-radius': '3px', 
                         
                    }
                ) for item in filters_store
            ],
            style={
                'textAlign': 'right', 
                'width': 'auto', 
                'display': 'flex',
                'justify-content': 'flex-start',
                'align-items': 'center'
            }
        )
    )



@app.callback(
    Output('filters_store', 'data'),
    Input({'type': 'delete-button_filter', 'index_ID': ALL}, 'n_clicks'),
    State({'type': 'delete-button_filter', 'index_ID': ALL}, 'id'),
    State('filters_store', 'data'),
    prevent_initial_call=True,
)
def delete_filter(delete_clicks, delete_button_ID, filters_store):
    for i, clicks in enumerate(delete_clicks):
        if clicks is not None and clicks > 0:
            index_id = delete_button_ID[i]
            index_id = index_id['index_ID']
            filters_store = [item for item in filters_store if item["filter_id"] != index_id]
            return filters_store

    return dash.no_update



@app.callback(
    Output('table_data_NORAD_id_filtered', 'data', allow_duplicate=True),
    Input('search-input', 'value'),
    Input('filters_store', 'data'),
    Input('new_object_added', 'data'),
    Input('new_object_deleted','data'),
    prevent_initial_call=True     
)
def update_table_data_w_filters (search_value, filters_store, new_object_added, new_object_deleted):
    global df

    filtered_df = df.copy()

    for filter in filters_store:
        variable = filter["variable"]
        operation = filter["operation"]
        value = filter["quantity"]

        if operation == "=":
            filtered_df = filtered_df[filtered_df[variable] == value]
        elif operation == ">":
            filtered_df = filtered_df[filtered_df[variable] > value]
        elif operation == "<":
            filtered_df = filtered_df[filtered_df[variable] < value]
        elif operation == "<=":
            filtered_df = filtered_df[filtered_df[variable] <= value]
        elif operation == ">=":
            filtered_df = filtered_df[filtered_df[variable] >= value]

    if search_value:
        filtered_df = filtered_df[
            filtered_df['OBJECT_NAME'].str.contains(search_value, case=False, na=False) | 
            filtered_df['OBJECT_ID'].str.contains(search_value, case=False, na=False)
        ]
        
    table_data_NORAD_id_filtered = filtered_df['NORAD_CAT_ID'].tolist()

    return table_data_NORAD_id_filtered



@app.callback(
    Output('object-table', 'children'),
    Output('page-number', 'children'),
    Output('next-page-button', 'n_clicks'),  
    Output('previous-page-button', 'n_clicks'), 
    Output('total_pages', 'children'),
    Input('previous-page-button', 'n_clicks'),
    Input('next-page-button', 'n_clicks'),
    Input('search-input', 'value'),
    Input('checked_objects_store', 'data'),
    Input('table_data_NORAD_id_filtered', 'data'),
    State('object-table', 'children'),
    State('page-number', 'children'),
    prevent_initial_call=True
)
def update_table(prev_clicks, next_clicks, search_value, stored_checked_values, 
                 table_data_NORAD_id_filtered, table_children, page_number):
    global df

    if not page_number:
        page_number = 1
    else:
        page_number = int(page_number.split()[-1])

    if next_clicks:
        page_number += next_clicks
    elif prev_clicks and page_number > prev_clicks:
        page_number -= prev_clicks
    elif search_value:
        page_number = 1  

    start = (page_number - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    paginated_NORAD_ID = table_data_NORAD_id_filtered[start:end]
    paginated_data = []
    for NORAD_ID in paginated_NORAD_ID:
        item = df[df['NORAD_CAT_ID']==NORAD_ID]
        paginated_data.append(item)
    total_pages = np.ceil(len(table_data_NORAD_id_filtered)/PAGE_SIZE)

    table_children = dmc.Table(
    [
        html.Tbody(
            [
                html.Tr(
                    [
                        html.Td(
                            dmc.Checkbox(
                                label="",
                                checked=row["NORAD_CAT_ID"].iloc[0] in stored_checked_values,
                                value=row["NORAD_CAT_ID"].iloc[0],
                                id={"type": "plot-checkbox", "index_ID": int(row["NORAD_CAT_ID"].iloc[0])},
                                style={'width': '20px'}
                            ),
                            style={'width': '20px'}
                        ),
                        html.Td(row["OBJECT_NAME"].iloc[0], style={'width': '250px'}),
                        html.Td(row["OBJECT_ID"].iloc[0], style={'width': '150px'}),
                        html.Td(
                            [                           
                                dmc.Button(
                                    DashIconify(icon="material-symbols:edit", width=23, color="gray"),
                                    id={'type': 'edit-button', 'index_ID': int(row["NORAD_CAT_ID"].iloc[0])},
                                    variant="light",
                                    size="compact-xs",
                                    radius="xl",
                                    color="gray",
                                    px=0,  
                                    m=0,
                                    style={"width": "26px", "height": "26px", "margin-right": "10px"}  
                                ) if row['OBJECT_ID'].iloc[0] == 'CREATED BY USER' else None,
                                dmc.HoverCard(
                                    shadow="md",
                                    style={"width": "26px", "height": "26px", "margin-right": "10px"},
                                    position = "left",
                                    children=[
                                        dmc.HoverCardTarget(
                                            [
                                                dmc.Button(
                                                    DashIconify(icon="mdi:eye", width=23, color="gray"),
                                                    id={'type': 'view-button', 'index_ID': int(row["NORAD_CAT_ID"].iloc[0])},
                                                    disabled = True,
                                                    variant="light",
                                                    size="compact-xs",
                                                    radius="xl",
                                                    color="gray",
                                                    px=0, 
                                                    m=0,
                                                    style={"width": "26px", "height": "26px","margin-right": "10px"}  
                                                ),
                                            ],
                                        ),
                                        dmc.HoverCardDropdown(
                                            [                                            
                                                dmc.Grid(
                                                    [
                                                        dmc.Col(
                                                            [
                                                                dmc.Text(
                                                                    f"a={row['SEMIMAJOR_AXIS'].iloc[0]}", 
                                                                    style={"textAlign": "left"}
                                                                ),
                                                                dmc.Text(
                                                                    f"e={row['ECCENTRICITY'].iloc[0]}", 
                                                                    style={"textAlign": "left"}
                                                                ),
                                                                dmc.Text(
                                                                    f"i={row['INCLINATION'].iloc[0]}", 
                                                                    style={"textAlign": "left"}
                                                                ),
                                                            ], span=6
                                                        ),
                                                        dmc.Col(
                                                            [
                                                                dmc.Text(
                                                                    f"Ω={row['RA_OF_ASC_NODE'].iloc[0]}", 
                                                                    style={"textAlign": "left"}
                                                                ),
                                                                dmc.Text(
                                                                    f"ω={row['ARG_OF_PERICENTER'].iloc[0]}", 
                                                                    style={"textAlign": "left"}
                                                                ),
                                                                dmc.Text(
                                                                    f"ν={row['TRUE_ANOMALY'].iloc[0]}", 
                                                                    style={"textAlign": "left"}
                                                                ),
                                                            ], span=6
                                                        ),
                                                    ]
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                dmc.Button(
                                    DashIconify(icon="material-symbols:cancel-outline", width=23, color="gray"),
                                    id={'type': 'delete-button_obj', 'index_ID': int(row["NORAD_CAT_ID"].iloc[0])},
                                    variant="light",
                                    size="compact-xs",
                                    radius="xl",
                                    color="gray",
                                    px=0, 
                                    m=0,
                                    style={"width": "26px", "height": "26px","margin-right": "10px"}  
                                ),
                            ],
                            style={
                                'textAlign': 'right', 
                                'width': 'auto', 
                                'display': 'flex',
                                'justify-content': 'flex-end',
                                'align-items': 'center'
                            },
                        ),
                    ]
                ) for row in paginated_data
            ]
        ),
    ],
    highlightOnHover=True,
    )

    return table_children, f"{page_number}", 0, 0, total_pages


@app.callback(
    Output('upload-output', 'children'),
    Output('new_object_added', 'data'),
    Output('upload-data', 'contents'),
    Input('upload-data', 'contents'),
    State('upload-data', 'filename'),
    prevent_initial_call=True
)
def update_output(contents, filename):
    if contents is None:
        return '', False, None
    
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)

    if 'json' in filename:
        data = json.loads(decoded.decode('utf-8'))
        
        if not isinstance(data, list):
            return 'Error: The JSON file should contain a list of dictionaries.', False, None
        
        required_keys = {
            "OBJECT_NAME", "SEMIMAJOR_AXIS", "ECCENTRICITY", "INCLINATION", "RA_OF_ASC_NODE",
            "ARG_OF_PERICENTER", "TRUE_ANOMALY", "EPOCH", "f-number", "Sensor Height",  "Sensor Width",
            "Camera Resolution", "Focal Length", "Quaternion Vector", "Quaternion Angle"
        }
        
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                return html.Div(f'Error: Item {i+1} is not a dictionary.'), False, None
            
            missing_keys = required_keys - set(item.keys())
            if missing_keys:
                text_output = f'Error: Item {i+1} is missing the following required keys: {", ".join(missing_keys)}'
                return text_output, False, None
        

        global df
        new_data = pd.DataFrame(data)
        new_data['NORAD_CAT_ID'] = range(df['NORAD_CAT_ID'].max() + 1, df['NORAD_CAT_ID'].max() + 1 + len(new_data))
        new_data['OBJECT_ID'] = 'CREATED BY USER'


        if 'length' not in new_data.columns:
            new_data['length'] = 0.35/1000  
        if 'diameter' not in new_data.columns:
            new_data['diameter'] = 0.2/1000 
        if 'span' not in new_data.columns:
            new_data['span'] = 0.5/1000
        if 'mass' not in new_data.columns:
            new_data['mass'] = 12            
        if 'shape' not in new_data.columns:
            new_data['shape'] = 'cyl'
        if 'OBJECT_TYPE' not in new_data.columns:
            new_data['OBJECT_TYPE'] = 'PAYLOAD'            
        
        df = pd.concat([new_data, df], ignore_index=True)
        
        return 'Successfully uploaded', True, None
    else:
        return 'Error: Please upload a JSON file.', False, None






@app.callback(
    Output('sat_name_created', 'value'),
    Output('semi_major_axis', 'value'),
    Output('ecc', 'value'),
    Output('inclination', 'value'),
    Output('long_asc_node', 'value'),
    Output('arg_peri', 'value'),
    Output('true_anomaly', 'value'),
    Output('epoch_orbit','value'),
    Output('f_number','value'),
    Output('sensor_width','value'),
    Output('sensor_height','value'),
    Output('cam_res','value'),
    Output('focal_length','value'),
    Output('quaternion_vector','value'),
    Output('quaternion_angle','value'),

    Output('sat_name_created', 'error'),
    Output('semi_major_axis', 'error'),
    Output('ecc', 'error'),
    Output('inclination', 'error'),
    Output('long_asc_node', 'error'),
    Output('arg_peri', 'error'),
    Output('true_anomaly', 'error'),
    Output('epoch_orbit', 'error'),
    Output('f_number','error'),
    Output('sensor_width','error'),
    Output('sensor_height','error'),
    Output('cam_res','error'),
    Output('focal_length','error'),
    Output('quaternion_vector','error'),
    Output('quaternion_angle','error'),  

    Output('create_objects_button', 'n_clicks'),
    Output('row_ID_store', 'data'),
    Input('modal_created_objects', 'opened'),
    Input('create_objects_button', 'n_clicks'),
    prevent_initial_call=True
)
def reset_inputs(modal_created_objects, create_objects_button_clicks):
    global df
    if modal_created_objects and create_objects_button_clicks is not None:
        max_norad_cat_id = df['NORAD_CAT_ID'].max()
        created_element_id = max_norad_cat_id + 1
        return ('', '', '', '', '', '', '', '', '', '', '', '', '', '', '',
                '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', None, created_element_id)
    else:
        return (dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, 
                dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, 
                dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, 
                dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, 
                dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, 
                dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update,
                dash.no_update, dash.no_update)



@app.callback(
    Output('new_object_added', 'data'),
    Output('creation_edition_output', 'data'),
    Output('sat_name_created', 'error'),
    Output('semi_major_axis', 'error'),
    Output('ecc', 'error'),
    Output('inclination', 'error'),
    Output('long_asc_node', 'error'),
    Output('arg_peri', 'error'),
    Output('true_anomaly', 'error'),
    Output('epoch_orbit', 'error'),
    Output('f_number','error'),
    Output('sensor_width','error'),
    Output('sensor_height','error'),
    Output('cam_res','error'),
    Output('focal_length','error'),
    Output('quaternion_vector','error'),
    Output('quaternion_angle','error'),    
    Output('sat_name_created', 'value'),
    Output('semi_major_axis', 'value'),
    Output('ecc', 'value'),
    Output('inclination', 'value'),
    Output('long_asc_node', 'value'),
    Output('arg_peri', 'value'),
    Output('true_anomaly', 'value'),
    Output('epoch_orbit', 'value'),
    Output('f_number','value'),
    Output('sensor_width','value'),
    Output('sensor_height','value'),
    Output('cam_res','value'),
    Output('focal_length','value'),
    Output('quaternion_vector','value'),
    Output('quaternion_angle','value'),

    Input('save_edited_created_button', 'n_clicks'),
    State('sat_name_created', 'value'),
    State('semi_major_axis', 'value'),
    State('ecc', 'value'),
    State('inclination', 'value'),
    State('long_asc_node', 'value'),
    State('arg_peri', 'value'),
    State('true_anomaly', 'value'),
    State('epoch_orbit', 'value'),
    State('f_number','value'),
    State('sensor_width','value'),
    State('sensor_height','value'),
    State('cam_res','value'),
    State('focal_length','value'),
    State('quaternion_vector','value'),
    State('quaternion_angle','value'),
    State('row_ID_store', 'data'),
)
def create_edit_object(n_clicks, sat_name, sma, ecc, inc, raan, arg_peri, true_anom, 
                       epoch_orbit, f_number, sensor_width, sensor_height, cam_res, 
                       focal_length, quaternion_vector, quaternion_angle, row_ID_store):
    global df
    if n_clicks:
        if sat_name == '':
            sat_name_error = 'This field must be fulfilled'        
        else:
            sat_name_error = ''

        if sma == '':
            sma_error = 'This field must be fulfilled'
        elif isinstance(sma, float) and isinstance(sma, int):
            sma_error = 'This field must be a float number'
        else:
            sma_error = ''

        if ecc == '':
            ecc_error = 'This field must be fulfilled'
        elif isinstance(ecc, float) and isinstance(ecc, int):
            ecc_error = 'This field must be a float number'
        else:
            ecc_error = ''

        if raan == '':
            raan_error = 'This field must be fulfilled'
        elif isinstance(raan, float) and isinstance(raan, int):
            raan_error = 'This field must be a float number'
        else:
            raan_error = ''

        if inc == '':
            inc_error = 'This field must be fulfilled'
        elif isinstance(inc, float) and isinstance(inc, int):
            inc_error = 'This field must be a float number'
        else:
            inc_error = ''

        if arg_peri == '':
            arg_peri_error = 'This field must be fulfilled'
        elif isinstance(arg_peri, float) and isinstance(arg_peri, int):
            arg_peri_error = 'This field must be a float number'
        else:
            arg_peri_error = ''

        if true_anom == '':
            true_anom_error = 'This field must be fulfilled'
        elif isinstance(true_anom, float) and isinstance(true_anom, int):
            true_anom_error = 'This field must be a float number'
        else:
            true_anom_error = ''

        if f_number == '':
            f_number_error = 'This field must be fulfilled'
        elif isinstance(f_number, float) and isinstance(f_number, int):
            f_number_error = 'This field must be a float number'
        else:
            f_number_error = ''
            
        if sensor_width == '':
            sensor_width_error = 'This field must be fulfilled'
        elif isinstance(sensor_width, float) and isinstance(sensor_width, int):
            sensor_width_error = 'This field must be a float number'
        else:
            sensor_width_error = ''

        if sensor_height == '':
            sensor_height_error = 'This field must be fulfilled'
        elif isinstance(sensor_height, float) and isinstance(sensor_height, int):
            sensor_height_error = 'This field must be a float number'
        else:
            sensor_height_error = ''

        if cam_res == '':
            cam_res_error = 'This field must be fulfilled'
        elif isinstance(cam_res, float) and isinstance(cam_res, int):
            cam_res_error = 'This field must be a float number'
        else:
            cam_res_error = ''

        if focal_length == '':
            focal_length_error = 'This field must be fulfilled'
        elif isinstance(focal_length, float) and isinstance(focal_length, int):
            focal_length_error = 'This field must be a float number'
        else:
            focal_length_error = ''

        if quaternion_angle == '':
            quaternion_angle_error = 'This field must be fulfilled'
        elif isinstance(quaternion_angle, float) and isinstance(quaternion_angle, int):
            quaternion_angle_error = 'This field must be a float number'
        else:
            quaternion_angle_error = ''

        if epoch_orbit == '':
            epoch_orbit_error = 'This field must be fulfilled'
        else:
            try:
                datetime.strptime(epoch_orbit, "%Y-%m-%dT%H:%M:%S.%f")
                epoch_orbit_error = ''
            except ValueError:
                epoch_orbit_error = 'This field must be a in format YYYY-MM-DDThh:mm:ss.f'             

        if quaternion_vector == '':
            quaternion_vector_error = 'This field must be fulfilled'
        else:
            pattern = r'^\[\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*\]$'
            match = re.match(pattern, quaternion_vector)
            if bool(match):
                quaternion_vector_error = ''
            else:
                quaternion_vector_error = 'This field must be a in format [x,y,z]'
        


        if (sat_name_error == '' and sma_error == '' and ecc_error == '' and inc_error == '' and
            raan_error == '' and arg_peri_error == '' and true_anom_error == '' and
            epoch_orbit_error == '' and f_number_error == '' and sensor_width_error == '' and
            sensor_height_error == '' and cam_res_error == '' and focal_length_error == '' and
            quaternion_vector_error == '' and quaternion_angle_error == ''):

            new_object = {
                'NORAD_CAT_ID': row_ID_store,
                'OBJECT_NAME': sat_name,
                'OBJECT_ID': 'CREATED BY USER',
                'SEMIMAJOR_AXIS': sma,
                'ECCENTRICITY': ecc,
                'INCLINATION': inc,
                'RA_OF_ASC_NODE': raan,
                'ARG_OF_PERICENTER': arg_peri,
                'TRUE_ANOMALY': true_anom,
                'EPOCH': epoch_orbit,
                'f-number': f_number,
                'Sensor Width': sensor_width,
                'Sensor Height': sensor_height,
                'Camera Resolution': cam_res,
                'Focal Length': focal_length,
                'Quaternion Vector': quaternion_vector,
                'Quaternion Angle': quaternion_angle,
                'length': 0.35/1000, #in km
                'diameter': 0.2/1000, #in km
                'span': 0.5/1000,
                'mass': 12,
                'shape': 'cyl',
                "OBJECT_TYPE": 'PAYLOAD',
            }
            new_df = pd.DataFrame([new_object])
            if row_ID_store in df['NORAD_CAT_ID'].values:
                for key, value in new_object.items():
                    if key in df.columns:
                        df.loc[df['NORAD_CAT_ID'] == row_ID_store, key] = value
            else:
                df = pd.concat([new_df, df], ignore_index=True)

            return (True, True, sat_name_error, sma_error, ecc_error, inc_error, raan_error, 
                    arg_peri_error, true_anom_error, epoch_orbit_error, f_number_error, 
                    sensor_width_error, sensor_height_error, cam_res_error, focal_length_error, 
                    quaternion_vector_error, quaternion_angle_error, sat_name, sma, ecc, inc, 
                    raan, arg_peri, true_anom, epoch_orbit, f_number, sensor_width, 
                    sensor_height, cam_res, focal_length, quaternion_vector, quaternion_angle)
        else: 
            return (False, False, sat_name_error, sma_error, ecc_error, inc_error, raan_error, 
                    arg_peri_error, true_anom_error, epoch_orbit_error, f_number_error, 
                    sensor_width_error, sensor_height_error, cam_res_error, focal_length_error, 
                    quaternion_vector_error, quaternion_angle_error, sat_name, sma, ecc, inc, 
                    raan, arg_peri, true_anom, epoch_orbit, f_number, sensor_width, 
                    sensor_height, cam_res, focal_length, quaternion_vector, quaternion_angle)

    return (False, False, '','','','','','','','','','','','','','','',
            sat_name, sma, ecc, inc, raan, arg_peri, true_anom, epoch_orbit, 
            f_number, sensor_width, sensor_height, cam_res, focal_length, 
            quaternion_vector, quaternion_angle)




@app.callback(
    Output("modal-objects", "opened"),
    Output("modal_created_objects", "opened"),
    State("modal-objects", "opened"),
    State("modal_created_objects", "opened"),        

    Output('sat_name_created', 'value'),
    Output('semi_major_axis', 'value'),
    Output('ecc', 'value'),
    Output('inclination', 'value'),
    Output('long_asc_node', 'value'),
    Output('arg_peri', 'value'),
    Output('true_anomaly', 'value'),
    Output('epoch_orbit', 'value'),
    Output('f_number','value'),
    Output('sensor_width','value'),
    Output('sensor_height','value'),
    Output('cam_res','value'),
    Output('focal_length','value'),
    Output('quaternion_vector','value'),
    Output('quaternion_angle','value'),
    Output('row_ID_store', 'data'),
    State({'type': 'edit-button', 'index_ID': ALL}, 'id'),
    Input({'type': 'edit-button', 'index_ID': ALL}, 'n_clicks'),
    prevent_initial_call=True,
)
def edit_object_modal(modal_objects_opened_state, modal_created_objects_opened_state, 
                      edit_button_ID ,edit_clicks):
    global df
    for i, clicks in enumerate(edit_clicks):
        if clicks is not None and clicks > 0:
            index_id = edit_button_ID[i]
            index_id = index_id['index_ID']
            object_data = df[df['NORAD_CAT_ID']==index_id]
            return (False, True,
                    object_data["OBJECT_NAME"].iloc[0], 
                    float(object_data["SEMIMAJOR_AXIS"].iloc[0]), 
                    float(object_data["ECCENTRICITY"].iloc[0]),
                    float(object_data["INCLINATION"].iloc[0]), 
                    float(object_data["RA_OF_ASC_NODE"].iloc[0]), 
                    float(object_data["ARG_OF_PERICENTER"].iloc[0]),
                    float(object_data["TRUE_ANOMALY"].iloc[0]),
                    object_data["EPOCH"].iloc[0] ,
                    float(object_data["f-number"].iloc[0]),
                    float(object_data["Sensor Width"].iloc[0]),
                    float(object_data["Sensor Height"].iloc[0]),
                    float(object_data["Camera Resolution"].iloc[0]),
                    float(object_data["Focal Length"].iloc[0]),
                    object_data["Quaternion Vector"].iloc[0],
                    float(object_data["Quaternion Angle"].iloc[0]),
                    object_data["NORAD_CAT_ID"].iloc[0])

    return (dash.no_update, dash.no_update, dash.no_update, dash.no_update, 
            dash.no_update, dash.no_update, dash.no_update, dash.no_update, 
            dash.no_update, dash.no_update, dash.no_update, dash.no_update, 
            dash.no_update, dash.no_update, dash.no_update, dash.no_update,  
            dash.no_update, dash.no_update)


@app.callback(
    Output('new_object_deleted', 'data'),
    Input({'type': 'delete-button_obj', 'index_ID': ALL}, 'n_clicks'),
    State({'type': 'delete-button_obj', 'index_ID': ALL}, 'id'),
    State('table_data_NORAD_id_filtered', 'data'),
    State('new_object_deleted', 'data'),
    prevent_initial_call=True
)
def delete_object(delete_clicks, delete_button_ID, table_data_NORAD_id_filtered, 
                  new_object_deleted):
    
    for i, clicks in enumerate(delete_clicks):
        if clicks is not None and clicks > 0:
            index_id = delete_button_ID[i]['index_ID']
            df.drop(df[df['NORAD_CAT_ID'] == index_id].index, inplace=True)
            new_object_deleted =+1
            return new_object_deleted



@app.callback(
    Output('checked_objects_store', 'data'),
    Output('all_elements', 'checked'),
    Input({'type': 'plot-checkbox', 'index_ID': ALL}, 'checked'),
    Input('all_elements', 'checked'),
    State('checked_objects_store', 'data'),
    State({'type': 'plot-checkbox', 'index_ID': ALL}, 'value'),
    Input('table_data_NORAD_id_filtered','data'),
    prevent_initial_call=True,
)
def update_checked_objects_store(checked, checked_all, checked_objects_store, 
                                 values, filtered_id_data):
    
    if checked_objects_store is None:
        checked_objects_store = []

    triggered_id = ctx.triggered_id
    
    if triggered_id != "all_elements":
        for i, chk in enumerate(checked):
            if chk and values[i] not in checked_objects_store:
                checked_objects_store.append(values[i])
            elif not chk and values[i] in checked_objects_store:
                checked_objects_store.remove(values[i])

        checked_objects_store = set(checked_objects_store)
        filtered_id_data = set(filtered_id_data)  
        if filtered_id_data.issubset(checked_objects_store):
            checked = True
        else:
            checked = False
        checked_objects_store = list(checked_objects_store)

    if triggered_id == "all_elements":
        checked_objects_store = set(checked_objects_store)
        filtered_id_data = set(filtered_id_data)
        if checked_all:
            checked_objects_store.update(filtered_id_data - checked_objects_store) 
            checked_objects_store = list(checked_objects_store)
            checked = True
        else:
            checked_objects_store.difference_update(filtered_id_data) 
            checked_objects_store = list(checked_objects_store)
            checked = False
      
    
    return checked_objects_store, checked



@app.callback(
    Output("propagation_id", "data"),
    Input("propagate_propagate_button", 'n_clicks'),
    State('checked_objects_store', 'data'),
    State('prop_time', 'value'),
    State('start_date_storage', 'data'),
    State('propagator_selection', 'value'),
    prevent_initial_call=True,
)
def propagate_selected_orbits(propagate_button, checked_objects, prop_time, 
                              start_date_storage, propagator_selection):
    
    global df,propagated_data_store
    if None in [prop_time, start_date_storage, propagator_selection]:
        return None
    else:
        propagation_id = f"{prop_time}-{start_date_storage}-{propagator_selection}"

        if propagation_id in propagated_data_store:
            return propagation_id

        start_date = Time(datetime.strptime(start_date_storage, "%Y-%m-%d %H:%M:%S.%f"), 
                          scale="utc", 
                          format="datetime"
                    )
        end_date = start_date + timedelta(minutes=prop_time)
        steps = int(prop_time)*10 #10 step every minute
        epochs = time_range(start_date, num_values=steps, end=end_date)
        time_step = prop_time/(steps-1)*60*1000 #time step in miliseconds

        jd, fr = to_julian(epochs) #this is for sgp4

        sun_gcrs = get_sun(epochs)
        # GCRS to TEME
        sun_teme = sun_gcrs.transform_to(TEME(obstime=epochs))
        x = sun_teme.cartesian.x
        y = sun_teme.cartesian.y
        z = sun_teme.cartesian.z

        sun_data = {
            'name': 'Sun',
            'coords': np.vstack((x.to(u.km).value, 
                                 y.to(u.km).value, 
                                 z.to(u.km).value)).T.tolist(),
            'epochs': [epoch.utc.iso for epoch in epochs]
        }

        table_data_store_propagated = []

        for sate in checked_objects:
            item = df[df['NORAD_CAT_ID'] == sate].iloc[0].to_dict() 
            orb_sat = Orbit.from_classical(Earth,
                                            float(item["SEMIMAJOR_AXIS"]) * u.km,
                                            float(item["ECCENTRICITY"]) * u.one,
                                            float(item["INCLINATION"]) * u.deg,
                                            float(item["RA_OF_ASC_NODE"]) * u.deg,
                                            float(item["ARG_OF_PERICENTER"]) * u.deg,
                                            float(item["TRUE_ANOMALY"]) * u.deg,
                                            Time(item["EPOCH"], scale='utc')
                                            )
            tofs = (epochs - orb_sat.epoch).to(u.s)
            rr, vv = propagate (orb_sat, epochs, tofs, method = propagator_selection, item=item, start_date=start_date, prop_time=prop_time, jd=jd, fr=fr)
            item['coords'] = rr
            if item ['OBJECT_ID'] == 'CREATED BY USER':
                quater_angle = float(item['Quaternion Angle'])
                quater_axis = ast.literal_eval(item ['Quaternion Vector'])
                orbit_axis_sys, body_axis_sys = get_coord_sys (rr,vv,quater_angle,quater_axis)
                item['bodyaxis'] = body_axis_sys
                item['orbitaxis'] = orbit_axis_sys

            table_data_store_propagated.append(item)

        propagated_data_store[propagation_id] = {
            "trajectory_data": table_data_store_propagated,
            "time_step": time_step,
            "sun_data": sun_data
        }
        
        return propagation_id

@app.callback(
    Output("plot_propagation_button", "disabled"),    
    Output("time-step-data", "data"),
    Output("sun-data", "data"), 
    Input("propagation_id", "data"),
    prevent_initial_call=True,
)
def update_visualization_sun_timestep(propagation_id):
    if propagation_id is None:
        return None, None, True
    else:
        data = propagated_data_store[propagation_id]
        time_step = data["time_step"]
        sun_data = data["sun_data"]        
        return False, time_step, sun_data



@app.callback(
    Output("trajectory-data", "data"), 
    State("propagation_id", "data"),
    Input("plot_propagation_button", "n_clicks"),
    prevent_initial_call=True,
)
def update_visualization(propagation_id, plot_propagation_button):
    if propagation_id is None:
        return None
    
    data = propagated_data_store[propagation_id]
    trajectory_data = data["trajectory_data"]

    return trajectory_data



app.clientside_callback(
    """
    function(sphereTrajectoryData, sceneInitiation, TimeStep, sunData) {
            window.initThreeScene(sphereTrajectoryData, TimeStep, sunData);
    }
    """,
    Output("threejs-container", "children"),
    Input("trajectory-data", "data"),
    Input("scene_initiation", "children"),
    State("time-step-data", "data"),
    State("sun-data", "data"),    
)
    

def process_created_sat(created_data, ephem_catalog_sat_data, sun_data):
    observation_from_created_sat, num_observations = get_observable_objects(created_data, 
                                                                            ephem_catalog_sat_data, 
                                                                            sun_data)
    summary = {
        "OBJECT_NAME": created_data['OBJECT_NAME'],
        "Number of Observations": num_observations,
        "NORAD_CAT_ID": created_data['NORAD_CAT_ID'] 
    }
    observation = {
        "NORAD_CAT_ID_observant": created_data['NORAD_CAT_ID'], 
        "observations": observation_from_created_sat
    }

    return summary, observation


@app.callback(
    Output('summary_table_trigger','data'),
    Input("propagation_id", "data"),
    State('summary_table_trigger','data'),
    prevent_initial_call=True,
)
def update_encounters_tab(propagation_id, summary_table_trigger):
    global propagated_data_store, observations, summary_data
    
    data = propagated_data_store[propagation_id]
    trajectory_data = data["trajectory_data"]
    sun_data = data["sun_data"]

    ephem_created_sat_data = []
    ephem_catalog_sat_data = []
    for item in trajectory_data:
        if item["OBJECT_ID"] == "CREATED BY USER":
            ephem_created_sat_data.append(item)
        else:
            ephem_catalog_sat_data.append(item)


    process_func = partial(process_created_sat, ephem_catalog_sat_data=ephem_catalog_sat_data, sun_data=sun_data)

    with multiprocessing.Pool() as pool:
        results = pool.map(process_func, ephem_created_sat_data)

    summary_data = [summary for summary, _ in results]
    observations = [observation for _, observation in results]

    summary_data.sort(key=lambda x: x["Number of Observations"], reverse=True)

    summary_table_trigger =+1

    return summary_table_trigger



@app.callback(
    Output('observant-summary-table', 'children'),
    Output('summary-pagination', 'total'),
    Output('summary-pagination', 'style'),
    Input("summary_table_trigger", "data"),
    Input('summary-pagination', 'value'),
)
def update_encounters_tab_summary_table(propagation_id, page):
    global propagated_data_store, observations, summary_data
    if propagation_id == None:
        return ("No data available, please press Add/Edit button and Propagate and Plot", 
            1, {'display': 'none'})

    start = (page - 1) * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    paginated_summary_data = summary_data[start:end]
    pagination_total = np.ceil(len(summary_data) / ITEMS_PER_PAGE),

    summary_table = dmc.Table(
        [
            html.Thead(
                html.Tr(
                    [
                        html.Th("Object Name"),
                        html.Th("Number of Observations"),
                        html.Th(""),
                    ]
                )
            ),
            html.Tbody(
                [
                    html.Tr(
                        [
                            html.Td(row["OBJECT_NAME"], 
                                    style={"padding": "0px 10px"}
                                    ),
                            html.Td(row["Number of Observations"], 
                                    style={"padding": "0px 10px"}
                                    ),
                            html.Td(
                                dmc.Button(
                                    "Details",
                                    id={'type': 'view-details-button', 
                                        'index_ID': row["NORAD_CAT_ID"]
                                        },
                                    size="xs",
                                    variant="light",
                                    style={"padding": "0px 5px", "height": "25px"}
                                ),
                                style={"padding": "0px 10px", "textAlign": "right"}
                            ),
                        ],
                        style={"height": "33px"}
                    ) for row in paginated_summary_data
                ]
            ),
        ],
        highlightOnHover=True,
    ) 

    return summary_table, pagination_total, {}



@app.callback(
    Output('detailed-observations-table', 'children'),
    Output('detailed-pagination', 'total'),
    Output({'type': 'view-details-button', 'index_ID': ALL}, 'n_clicks'),
    Input({'type': 'view-details-button', 'index_ID': ALL}, 'n_clicks'),
    State({'type': 'view-details-button', 'index_ID': ALL}, 'id'),
    Input('detailed-pagination', 'value'),
    State('time-step-data', 'data'),
    prevent_initial_call=True
)
def update_detailed_table(view_clicks, view_id, page, time_step):
    global observations
    
    observant_NORAD_ID = None
    reset_clicks = [None for _ in view_clicks]

    for i, clicks in enumerate(view_clicks):
        if clicks is not None and clicks > 0:
            observant_NORAD_ID = view_id[i]['index_ID']
            reset_clicks = [None for _ in view_clicks]
            break


    if observant_NORAD_ID is None:
        return "No satellite selected", 1, reset_clicks

    for item in observations:
        if item['NORAD_CAT_ID_observant'] == observant_NORAD_ID:
            observations_selected_sat = item['observations']
            break

    detailed_data = [
        {
            "To Object ID": obs["To Object ID"],
            "Observation Time(min)": (round(len(obs['Index_observable'])*time_step/60000, 2) 
                                      if len(obs['Index_observable']) > 1 
                                      else f"less than {round(time_step/60000, 2)}"
                                      ),
            "Closest Distance (km)": obs["Closest Distance (km)"],
            "Time of Closest Approach": obs['Time of Closest Approach'],
            "NORAD_CAT_ID_observed": obs['NORAD_CAT_ID_observed']
        } for obs in observations_selected_sat
    ]

    start = (page - 1) * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    paginated_detailed_data = detailed_data[start:end]
    pagination_total = np.ceil(len(detailed_data) / ITEMS_PER_PAGE),

    detailed_table = dmc.Table(
        [
            html.Thead(
                html.Tr(
                    [
                        html.Th("Observed Sat Object ID"),
                        html.Th("Observation Time(min)"),
                        html.Th("Closest Distance (km)"),
                        html.Th("Time of Closest Approach"),
                        html.Th(""),
                    ]
                )
            ),
            html.Tbody(
                [
                    html.Tr(
                        [
                            html.Td(row["To Object ID"], 
                                    style={"padding": "0px 10px"}
                                    ),
                            html.Td(row["Observation Time(min)"], 
                                    style={"padding": "0px 10px"}
                                    ),
                            html.Td(f"{row['Closest Distance (km)']:.2f}", 
                                    style={"padding": "0px 10px"}
                                    ),
                            html.Td(row["Time of Closest Approach"], 
                                    style={"padding": "0px 10px"}
                                    ),
                            html.Td(
                                dmc.Button(
                                    "Simulate",
                                    id={'type': 'view-image-button', 
                                        'ID_observed': row["NORAD_CAT_ID_observed"], 
                                        'ID_observant': observant_NORAD_ID
                                    },
                                    size="xs",
                                    variant="light",
                                    style={"padding": "0px 5px", "height": "25px"}
                                ),
                                style={"padding": "0px 10px", "textAlign": "right"}
                            ),
                        ],
                        style={"height": "33px"}
                    ) for row in paginated_detailed_data
                ]
            ),
        ],
        highlightOnHover=True,
    )

    return detailed_table, pagination_total, reset_clicks



@app.callback(
    Output('detailed-pagination', 'style'),
    Input('detailed-observations-table', 'children'),
)
def toggle_detailed_pagination_visibility(table_content):
    if isinstance(table_content, dict):
        return {}

    return {'display': 'none'}



@app.callback(
    Output('encounter_data_simulation', 'data'),
    Output('trajectory-data-simulation','data'),
    Output('sun-data-sim','data'),
    Output("time-step-data-sim", "data"),
    Output({'type': 'view-image-button', 'ID_observed': ALL, 'ID_observant': ALL}, 'n_clicks'),
    Input({'type': 'view-image-button', 'ID_observed': ALL, 'ID_observant': ALL}, 'n_clicks'),
    State({'type': 'view-image-button', 'ID_observed': ALL, 'ID_observant': ALL}, 'id'),
    State('propagation_id', 'data'),
    State('propagator_selection', 'value'),
    prevent_initial_call=True
)
def update_data_for_simulation(simulation_clicks, simulation_id, propagation_id, propagator_selection):
    global observations

    observed_norad_id = None
    observant_norad_id = None

    clicked_button = None
    for i, clicks in enumerate(simulation_clicks):
        if clicks is not None and clicks > 0:
            observant_norad_id = simulation_id[i]['ID_observant']
            observed_norad_id = simulation_id[i]['ID_observed']
            clicked_button = i
            break

    if clicked_button is None:
        return dash.no_update
    
    trajectory_data_simulation = []
    for item in observations:
        if item['NORAD_CAT_ID_observant'] == observant_norad_id:
            observations_observant_sat = item['observations']
            for item_ in observations_observant_sat:
                if item_['NORAD_CAT_ID_observed'] == observed_norad_id:
                    #Propagate for 1 second before and after the epoch of closest approach with 1000 steps per second.
                    #This will simulate a 1000 frames per second camera
                    epoch_closest = Time(datetime.strptime(item_["Time of Closest Approach"], 
                                                           "%Y-%m-%d %H:%M:%S.%f"), 
                                                           scale="utc", format="datetime")
                    start_time = epoch_closest - timedelta(seconds=20)                   
                    end_time = epoch_closest + timedelta(seconds=10)
                    prop_time_sim = (end_time - start_time).to(u.min).value
                    steps = 30*1000+1
                    epochs_sim = time_range(start_time, num_values=steps, end=end_time)
                    time_step = prop_time_sim/(steps-1)*60*1000 
                    jd, fr = to_julian(epochs_sim)

                    sun_gcrs_sim = get_sun(epochs_sim)
                    # GCRS to TEME
                    sun_teme_sim = sun_gcrs_sim.transform_to(TEME(obstime=epochs_sim))
                    x_sim = sun_teme_sim.cartesian.x
                    y_sim = sun_teme_sim.cartesian.y
                    z_sim = sun_teme_sim.cartesian.z

                    sun_data_sim = {
                        'name': 'Sun',
                        'coords': np.vstack((x_sim.to(u.km).value, 
                                            y_sim.to(u.km).value, 
                                            z_sim.to(u.km).value)).T.tolist(),
                        'epochs': [epoch_sim.utc.iso for epoch_sim in epochs_sim]
                    }

                    item_observed = df[df['NORAD_CAT_ID'] == observed_norad_id].iloc[0].to_dict() 
                    item_observant = df[df['NORAD_CAT_ID'] == observant_norad_id].iloc[0].to_dict() 
                    orb_sat_observed = Orbit.from_classical(Earth,
                                                            float(item_observed["SEMIMAJOR_AXIS"]) * u.km,
                                                            float(item_observed["ECCENTRICITY"]) * u.one,
                                                            float(item_observed["INCLINATION"]) * u.deg,
                                                            float(item_observed["RA_OF_ASC_NODE"]) * u.deg,
                                                            float(item_observed["ARG_OF_PERICENTER"]) * u.deg,
                                                            float(item_observed["TRUE_ANOMALY"]) * u.deg,
                                                            Time(item_observed["EPOCH"], scale='utc')
                                                            )
                    orb_sat_observant = Orbit.from_classical(Earth,
                                                            float(item_observant["SEMIMAJOR_AXIS"]) * u.km,
                                                            float(item_observant["ECCENTRICITY"]) * u.one,
                                                            float(item_observant["INCLINATION"]) * u.deg,
                                                            float(item_observant["RA_OF_ASC_NODE"]) * u.deg,
                                                            float(item_observant["ARG_OF_PERICENTER"]) * u.deg,
                                                            float(item_observant["TRUE_ANOMALY"]) * u.deg,
                                                            Time(item_observant["EPOCH"], scale='utc')
                                                            )
                    tofs_observed = (epochs_sim - orb_sat_observed.epoch).to(u.s)
                    tofs_obsevant = (epochs_sim - orb_sat_observant.epoch).to(u.s)
                    rr_observed, vv_observed = propagate (orb_sat_observed,epochs_sim,tofs_observed, 
                                                          method=propagator_selection, item=item_observed, 
                                                          start_date=start_time, prop_time=prop_time_sim, jd=jd, fr=fr)
                    rr_observant, vv_observant = propagate (orb_sat_observant,epochs_sim,tofs_obsevant, 
                                                            method='Farnocchia', item=item_observant,
                                                            start_date=start_time, prop_time=prop_time_sim, jd=jd, fr=fr)
                    item_observed['coords'] = rr_observed
                    item_observant['coords'] = rr_observant
                    quater_angle_sim = float(item_observant['Quaternion Angle'])
                    quater_axis_sim = ast.literal_eval(item_observant['Quaternion Vector'])
                    orbit_axis_sys_sim, body_axis_sys_sim = get_coord_sys (rr_observant,vv_observant,quater_angle_sim,quater_axis_sim)
                    item_observant['bodyaxis'] = body_axis_sys_sim
                    item_observant['orbitaxis'] = orbit_axis_sys_sim

                    trajectory_data_observant = item_observant
                    trajectory_data_simulation.append(trajectory_data_observant)
                    trajectory_data_observed = item_observed
                    trajectory_data_simulation.append(trajectory_data_observed)

                    reset_clicks = [None if i == clicked_button else clicks 
                                    for i, clicks in enumerate(simulation_clicks)]
                    return item_, trajectory_data_simulation, sun_data_sim, time_step, reset_clicks

    return dash.no_update
    


app.clientside_callback(
    """
    function(encounterData, sphereTrajectoryData, TimeStep, sunData) {
            window.initViewScene(encounterData, sphereTrajectoryData, TimeStep, sunData);
    }
    """,
    Output("3d_camera_sight_sim", "children"),
    Input('encounter_data_simulation', 'data'),
    State("trajectory-data-simulation", "data"),
    State("time-step-data-sim", "data"),
    State("sun-data-sim", "data"),

)


app.clientside_callback(
    """
    function(encounterData, sphereTrajectoryData, TimeStep, sunData) {
            window.initEventScene(encounterData, sphereTrajectoryData, TimeStep, sunData);
    }
    """,
    Output("event_cam_image", "children"),
    Input('encounter_data_simulation', 'data'),
    State("trajectory-data-simulation", "data"),
    State("time-step-data-sim", "data"),
    State("sun-data-sim", "data"),

)


if __name__ == '__main__':
    app.run(debug=True)