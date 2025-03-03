from dash import html, dcc
from dash import dcc
from dash_iconify import DashIconify
import dash_mantine_components as dmc

import textwrap

from astropy.time import Time


layout = dcc.Loading([
    html.Div([
        dcc.Store(id='start_date_storage', data=str(Time(Time.now(), scale="utc", format="datetime"))),
        dcc.Store(id='checked_objects_store', data=[]),
        dcc.Store(id='filters_store', data=[]),
        dcc.Store(id='table_data_NORAD_id_filtered', data=[]),
        dcc.Store(id='row_ID_store', data=''),
        dcc.Store(id='new_object_added'),
        dcc.Store(id='creation_edition_output'),
        dcc.Store(id='new_object_deleted'),
        dcc.Store(id='propagation_id', data=''),
        dcc.Store(id="trajectory-data", data=[{}]),
        dcc.Store(id="trajectory-data-simulation", data=[{}]),
        dcc.Store(id="time-step-data"),
        dcc.Store(id="sun-data"),
        dcc.Store(id="time-step-data-sim"),
        dcc.Store(id="sun-data-sim"),
        dcc.Store(id="encounter_data_simulation", data={}),
        dcc.Store(id="summary_table_trigger"),
        html.Div(id="scene_initiation"),

        dmc.Grid([
            dmc.Col([
                dmc.Container([
                    dmc.Title('EventSat', color="blue", size="h2"),
                    dmc.Space(h=20),
                    dmc.Group(
                        [
                            dmc.Button("Add/edit objects", id="more_objects_button"),
                            dmc.Button("Plot propagation", id="plot_propagation_button", disabled = True)
                        ],position="center",
                    ),

                    dmc.Modal(
                        id="modal-objects",
                        size="40%",
                        zIndex=10000,
                        children=[
                            dmc.Group([
                                dmc.Button(
                                    DashIconify(icon="material-symbols:upload", width=23, color="white"),
                                    id = 'upload_new_objects',
                                    px=5, 
                                ),
                                dmc.Button("Create object", id="create_objects_button"),
                            ], position="right"),
                            dmc.Space(h=10),
                            dmc.Group([
                                dmc.Popover(
                                    [
                                        dmc.PopoverTarget(
                                            dmc.Button(
                                                "Filter", 
                                                id='filter_search', 
                                                leftIcon=DashIconify(icon="material-symbols:filter-alt"), 
                                                style={"width": '100px'}
                                            ),
                                        ),
                                        dmc.PopoverDropdown(
                                            [
                                                dmc.Grid(
                                                    [
                                                        dmc.Select(
                                                            label="Variable to filter",
                                                            placeholder="Select one",
                                                            id="variable_filter",
                                                            value="a",
                                                            data=[
                                                                {"value": "SEMIMAJOR_AXIS", 
                                                                 "label": "Semimajor Axis"
                                                                },
                                                                {"value": "ECCENTRICITY", 
                                                                 "label": "Eccentricity"
                                                                },
                                                                {"value": "INCLINATION", 
                                                                 "label": "Inclination"
                                                                },
                                                                {"value": "RA_OF_ASC_NODE", 
                                                                 "label": "RAAN"
                                                                },
                                                                {"value": "ARG_OF_PERICENTER", 
                                                                 "label": "Argument of periapsis"
                                                                },
                                                                {"value": "TRUE_ANOMALY", 
                                                                 "label": "True anomaly"
                                                                },
                                                            ],
                                                            style={"width": 200, "marginRight": 5},
                                                        ),
                                                        dmc.Select(
                                                            label="Operation",
                                                            placeholder="Select one",
                                                            id="operation_filter",
                                                            value="=",
                                                            data=[
                                                                {"value": "=", "label": "="},
                                                                {"value": ">", "label": ">"},
                                                                {"value": "<", "label": "<"},
                                                                {"value": ">=", "label": "≥"},
                                                                {"value": "<=", "label": "≤"},
                                                            ],
                                                            style={"width": 70, "marginRight": 5},
                                                        ),  
                                                        dmc.NumberInput(
                                                            label="Quantity",
                                                            id='quantity_filter',
                                                            precision=6,
                                                            style={"width": 150, "marginRight": 5},
                                                        ),
                                                        dmc.Container(
                                                            dmc.Button(
                                                                "Save", 
                                                                id="save_filter_button", 
                                                                color="blue", 
                                                                variant="outline", 
                                                                size="sm",
                                                                style={"width": 100}
                                                            ),
                                                            px = 0,  
                                                            style={
                                                                "display": "flex", 
                                                                "flex-direction": "column", 
                                                                "justify-content": "flex-end"
                                                                }
                                                        ),                                     
                                                    ],
                                                ),
                                            ],
                                        ),
                                    ],
                                    width='auto', position="bottom-start", withArrow=True, shadow="md",
                                ),
                                dmc.TextInput(
                                    id='search-input', 
                                    placeholder='Search by Object Name or ID', 
                                    style={"flex": 1}
                                ),
                            ], style={"width": '75%', "display": 'flex'}),
                            dmc.Space(h=15),
                            dmc.Container(id='filters_badge', style = {'width': 'auto'}),
                            dmc.Space(h=15),
                            dmc.Table(
                                [
                                    html.Thead(
                                        html.Tr(
                                            [
                                                html.Th(
                                                    dmc.Checkbox(
                                                        label="",
                                                        checked= "",
                                                        id='all_elements',
                                                        style={'width': '20px'}
                                                    ),
                                                    style={'width': '20px'}                        
                                                ),
                                                html.Th("Object Name", style={'width': '250px'}),
                                                html.Th("Object ID", style={'width': '150px'}),
                                                html.Th("", style={'width': 'auto'}),
                                            ]
                                        ),
                                    ),
                                ],
                            ),
                            dcc.Loading(
                                html.Div(id='object-table'),
                            ),
                            dmc.Space(h=5),
                            dmc.Group([
                                dmc.Button(
                                    "<", 
                                    id='previous-page-button', 
                                    variant="outline", 
                                    size="xs"
                                ),
                                dmc.Text(id='page-number'),
                                dmc.Text("/"),
                                dmc.Text(id='total_pages'),
                                dmc.Button(
                                    ">", 
                                    id='next-page-button', 
                                    variant="outline", 
                                    size="xs"
                                ),
                            ], position="right"),
                            dmc.Space(h=30),
                            dmc.Group([
                                dmc.Button(
                                    "Propagate", 
                                    id="propagate_button", 
                                    color="blue", 
                                    size="md"
                                ),
                            ], position="right"),
                        ],
                    ),

                    dmc.Modal(
                        id="modal-upload",
                        size="lg",
                        zIndex=10000,
                        children=[
                            dmc.Title("Upload New Objects", order=4),
                            dmc.Text("Upload a JSON file containing a list of dictionaries with the following keys."),
                            dmc.Text("Example (substitute the comments after the colons with the quantities):"),
                            dmc.Space(h=10),
                            dmc.Text(
                                dmc.Prism(
                                    textwrap.dedent(
                                        """
                                        [
                                            {
                                                "OBJECT_NAME": *Type: String*,
                                                "SEMIMAJOR_AXIS": *Type: float. Units: kilometers*,
                                                "ECCENTRICITY": *Type: float. Units: degrees*,
                                                "INCLINATION": *Type: float. Units: degrees*,
                                                "RA_OF_ASC_NODE": *Type: float. Units: degrees*,
                                                "ARG_OF_PERICENTER": *Type: float. Units: degrees*,
                                                "TRUE_ANOMALY": *Type: float. Units: degrees*,
                                                "EPOCH": *Type: String. Format: YYYY-DD-MMThh:mm:ss.f*,
                                                "f-number": *Type: float. Units: adimensional*,
                                                "Sensor Width": *Type: float. Units: mm*,
                                                "Sensor Height": *Type: float. Units: mm*,
                                                "Camera Resolution": *Type: float. Units: MegaPixels*,
                                                "Focal Length": *Type: float. Units: mm*,
                                                "Quaternion Vector": *Type: String, Format: [x,y,z]*,
                                                "Quaternion Angle": *Type: float. Units: degrees*,
                                            }
                                        ]
                                        """
                                    ),
                                    language="json",
                                ),
                                style={"width": "100%"},
                            ),
                            dmc.Space(h=20),
                            dcc.Upload(
                                id='upload-data',
                                children=html.Div(
                                    [
                                        'Drag and Drop or ',
                                        html.A('Select Files')
                                    ],
                                    style={
                                        'fontFamily': 'Arial'
                                    }
                                ),
                                style={
                                    'width': '100%',
                                    'height': '60px',
                                    'lineHeight': '60px',
                                    'borderWidth': '2px',
                                    'borderColor': '#228be6',
                                    'borderStyle': 'dashed',
                                    'borderRadius': '5px',
                                    'textAlign': 'center',
                                    'margin': '10px 0'
                                },
                                multiple=False
                            ),
                            dmc.Space(h=5),
                            html.Div(id='upload-output',style={'fontFamily': 'Arial'}),
                        ],
                    ),
                    
                    dmc.Modal(
                        id="modal_created_objects",
                        size="35%",
                        zIndex=10000,
                        children=[
                            dmc.TextInput(id='sat_name_created', 
                                        label='Name of object', 
                                        placeholder='Enter name for satellite', 
                                        value='',
                                        error = '',
                                        ),
                            dmc.Space(h=15),
                            dmc.Grid([
                                dmc.Col([
                                    dmc.Text("Classical orbital parameters"),
                                    dmc.Space(h=5),
                                    dmc.NumberInput(label="Semi-major axis",
                                                    description="Units: kilometers",
                                                    precision=4,
                                                    id='semi_major_axis',
                                                    value='',
                                                    error = '',
                                    ),
                                    dmc.NumberInput(label="Eccentricity",
                                                    precision=4,
                                                    id='ecc',
                                                    value='',
                                                    error = '',
                                    ),
                                    dmc.NumberInput(label="Inclination",
                                                    description="Units: degrees",
                                                    precision=4,
                                                    id='inclination',
                                                    value='',
                                                    error = '',
                                    ),
                                    dmc.NumberInput(label="Longitude of the ascending node ",
                                                    description="Units: degrees",
                                                    precision=4,
                                                    id='long_asc_node',
                                                    value='',
                                                    error = '',
                                    ),
                                    dmc.NumberInput(label="Argument of periapsis ",
                                                    description="Units: degrees",
                                                    precision=4,
                                                    id='arg_peri',
                                                    value='',
                                                    error = '',
                                    ),
                                    dmc.NumberInput(label="True anomaly ",
                                                    description="Units: degrees",
                                                    precision=4,
                                                    id='true_anomaly',
                                                    value='',
                                                    error = '',              
                                    ),
                                    dmc.TextInput(label="Epoch at COE measurements ",
                                                description="Units: UTC time. Format: YYYY-MM-DDThh:mm:ss.f",
                                                id='epoch_orbit',
                                                value='',    
                                                error = '',          
                                    ),
                                ], span = 5),
                                dmc.Col([
                                    dmc.Text("Camera parameters"),
                                    dmc.Space(h=5),
                                    dmc.NumberInput(label="f-number",
                                                    precision=4,
                                                    id='f_number',
                                                    value='',
                                                    error = '',
                                    ),
                                    dmc.Group(
                                        [
                                            dmc.NumberInput(label="Sensor Width",
                                                            description="Units: mm",
                                                            precision=4,
                                                            id='sensor_width',
                                                            value = '',
                                                            error = '',
                                                            style={'width': '45%'},
                                            ),
                                            dmc.NumberInput(label="Sensor Height",
                                                            description="Units: mm",
                                                            precision=4,
                                                            id='sensor_height',
                                                            value = '',
                                                            error = '',
                                                            style={'width': '45%'},
                                            )
                                        ],
                                        position="center",  
                                        grow = True
                                    ),
                                    dmc.NumberInput(label="Camera Resolution",
                                                    description="Units: MegaPixels",
                                                    precision=4,
                                                    id='cam_res',
                                                    value = '',
                                                    error = '',
                                    ),                                
                                    dmc.NumberInput(label="Focal length",
                                                    description="Units: mm",
                                                    precision=4,
                                                    id='focal_length',
                                                    value='',
                                                    error = '',
                                    ),   
                                    dmc.Space(h=20),
                                    dmc.Text("Quaternion definition"), 
                                    dmc.TextInput(label="Rotation axis",
                                                id='quaternion_vector',
                                                description="Format: [x,y,z]",
                                                value='',
                                                error = '',
                                    ),   
                                    dmc.NumberInput(label="Rotation angle in degrees",
                                                    id='quaternion_angle',
                                                    description="Units: degrees",
                                                    precision=4,
                                                    value='',
                                                    error = '',
                                    ),                                                                                                            
                                ], span = 5),
                            ], justify="space-around", ),
                            dmc.Space(h=30),
                            dmc.Group([
                                dmc.Button("Save", 
                                           id="save_edited_created_button", 
                                           color="blue", 
                                           variant="outline", 
                                           size="md"
                                            )
                            ], position="right"),
                        ],
                    ),

                    dmc.Modal(
                        id="modal_propagation",
                        size="20%",
                        zIndex=10000,
                        children=[
                            dmc.Text("Propagation settings", size="sm"),
                            dmc.Select(
                                label="Select propagator",
                                placeholder="farnocchia",
                                id="propagator_selection",
                                value="Farnocchia",
                                data=[
                                    {"value": "Farnocchia", "label": "Farnocchia"},
                                    {"value": "Cowell (wo/perturbations)", "label": "Cowell (wo/perturbations)"},
                                    {"value": "Cowell (w/ some perturbations)", "label": "Cowell (w/ some perturbations)"},
                                    {"value": "Cowell (w/ perturbations)", "label": "Cowell (w/ perturbations)"},
                                    {"value": "Danby", "label": "Danby"},
                                    {"value": "Pimienta", "label": "Pimienta"},
                                    {"value": "Vallado", "label": "Vallado"},
                                    {"value": "SGP4", "label": "SGP4"},
                                ],
                                style={"width": 350, "marginRight": 5},
                            ),
                            dmc.Text("Initial epoch", size="sm"),
                            dmc.RadioGroup(
                                [
                                    dmc.Radio('Current time', value='Current time'),
                                    dmc.Space(h=10),
                                    dmc.Radio('Select time', value='Select time')
                                ],
                                id='initial_epoch_selection_group',
                                value='Current time',
                                size="sm",
                                mt=5,
                            ),
                            dmc.TextInput(
                                id='date_input',
                                label='Select time',
                                value=str(Time(Time.now(), scale="utc", format="datetime")),
                                disabled=True,
                            ),
                            dmc.NumberInput(label="Propagation time",
                                            description="Units: minutes",
                                            precision=4,
                                            id='prop_time',
                                            value=100,
                            ),
                            dmc.Space(h=15),
                            dmc.Group([
                                dmc.Button("Propagate", 
                                           id="propagate_propagate_button", 
                                           color="blue", 
                                           variant="outline", 
                                           size="md"
                                           )
                            ], position="right"),
                        ],
                    ),

                ], px="xs")
            ], span=2),
            dmc.Col([
                dmc.Tabs(
                    [
                        dmc.TabsList(
                            [
                                dmc.Tab("Plots", value="orbit_plots_tab"),
                                dmc.Tab("Encounters", value="encounters_tab"),
                            ]
                        ),
                        dmc.TabsPanel(
                            html.Div([
                                html.Div(id="threejs-container", 
                                         style={"width": "100%", 
                                                "height": "100%", 
                                                "margin": "0 auto", 
                                                "overflow": "hidden", 
                                                "position": "relative"
                                                }),
                            ], style={'height': '100%', 
                                      'padding': '2vh', 
                                      'margin-bottom': '2vh'
                                      }),
                            value="orbit_plots_tab",
                            style={'height': 'calc(100vh - 100px)'}
                        ),
                        dmc.TabsPanel(
                            html.Div([
                                dmc.Grid([
                                    dmc.Col([
                                        dmc.Card(
                                            children=[
                                                dmc.CardSection(
                                                    children= [
                                                        dmc.Text("Observant Satellites Summary", 
                                                                 weight=500
                                                                 )
                                                    ],
                                                    inheritPadding=True,
                                                    withBorder=True,
                                                    mt="sm",
                                                    pb="md",
                                                    py="xs",
                                                ),
                                                dmc.CardSection(
                                                    children= [
                                                        html.Div(id="observant-summary-table"),
                                                        dmc.Space(h=15),
                                                        dmc.Group([
                                                            dmc.Pagination(
                                                                id='summary-pagination', 
                                                                total=1, 
                                                                value=1, 
                                                                size="sm", 
                                                                withEdges=True
                                                            )                                                      
                                                        ], position="right")
                                                    ],
                                                    inheritPadding=True,
                                                    mt="sm",
                                                    pb="md",
                                                ),
                                            ],
                                            withBorder=True,
                                            shadow="sm",
                                            radius="md",
                                            style={"height": "50%"}
                                        ),
                                        dmc.Space(h=15),
                                        dmc.Card(
                                            children=[
                                                dmc.CardSection(
                                                    children= [
                                                        dmc.Text("Detailed Observations", 
                                                                 weight=500
                                                                 )
                                                    ],
                                                    inheritPadding=True,
                                                    withBorder=True,
                                                    mt="sm",
                                                    pb="md",
                                                    py="xs",
                                                ),
                                                dmc.CardSection(
                                                    children= [
                                                        html.Div(id="detailed-observations-table"),
                                                        dmc.Space(h=15),
                                                        dmc.Group([
                                                            dmc.Pagination(
                                                                id='detailed-pagination', 
                                                                total=1, 
                                                                value=1, 
                                                                size="sm", 
                                                                withEdges=True 
                                                            )
                                                        ], position="right")
                                                    ],
                                                    inheritPadding=True,
                                                    mt="sm",
                                                    pb="xs",
                                                ),
                                            ],
                                            withBorder=True,
                                            shadow="sm",
                                            radius="md",
                                            style={"height": "50%"}
                                        ),
                                    ], span=6, style={"height": "100%"}),
                                    dmc.Col([
                                        dmc.Card(
                                            children=[
                                                dmc.CardSection(
                                                    children= [
                                                        dmc.Text("3D Environment Simulation", weight=500)
                                                    ],
                                                    inheritPadding=True,
                                                    withBorder=True,
                                                    mt="sm",
                                                    pb="md",
                                                    py="xs",
                                                ),
                                                dmc.CardSection(
                                                    children= [
                                                        html.Div(
                                                            id="3d_camera_sight_sim", 
                                                            style={"height": "100%", "width":"100%"}
                                                        )
                                                    ], 
                                                    style={"flex": "1", 
                                                           "display": "flex", 
                                                           "flexDirection": "column"
                                                           },
                                                    inheritPadding=True,
                                                    mt="sm",
                                                    mb="sm",
                                                    pb="md",
                                                ),
                                            ],
                                            withBorder=True,
                                            shadow="sm",
                                            radius="md",
                                            style={"height": "50%", 
                                                   "display": "flex", 
                                                   "flexDirection": "column"
                                                   }
                                        ),
                                        dmc.Space(h=15),
                                        dmc.Card(
                                            children=[
                                                dmc.CardSection(
                                                    children= [
                                                        dmc.Text("Event Sensor Image Simulation", 
                                                                 weight=500
                                                                 )
                                                    ],
                                                    inheritPadding=True,
                                                    withBorder=True,
                                                    mt="sm",
                                                    pb="md",
                                                    py="xs",
                                                ),
                                                dmc.CardSection(
                                                    children= [
                                                        html.Div(
                                                            id="event_cam_image", 
                                                            style={"height": "100%", 
                                                                   "width":"100%"
                                                                   }
                                                        )
                                                    ],
                                                    style={"flex": "1", 
                                                           "display": "flex", 
                                                           "flexDirection": "column"
                                                           },
                                                    inheritPadding=True,
                                                    mt="sm",
                                                    mb="sm",
                                                    pb="md",
                                                ),
                                            ],
                                            withBorder=True,
                                            shadow="sm",
                                            radius="md",
                                            style={"height": "50%", 
                                                   "display": "flex", 
                                                   "flexDirection": "column"
                                                   }
                                        ),
                                    ], span=6, style={'height': '100%'}),
                                ], style={'height': '100%'} ),
                            ], style={'height': '100%'}),
                            value="encounters_tab",
                            style={'height': 'calc(100vh - 100px)', 
                                   'padding': '20px'
                                   },
                        ),
                    ],
                    value="orbit_plots_tab",
                    orientation="horizontal",
                    style={'height': '100%'}
                ),
            ], span=10, style={'height': 'calc(100vh - 50px)'}),
        ]),
    ], style={'height': '100%'})
], 
overlay_style={"visibility":"visible", "opacity": .5, "backgroundColor": "white"}, 
target_components={"propagation_id": "data", 
                   "summary_table_trigger":"data", 
                   "trajectory-data":"data", 
                   "sun-data":"data"
                   }
)

