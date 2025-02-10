from dash import Dash, dcc, callback, Output, Input, _dash_renderer
import plotly.express as px
import dash_mantine_components as dmc
import os # Used to get passwords
import dash_auth # Used for password protection
from config import DASHBOARD_USER, DASHBOARD_PW

# Enable Matine
_dash_renderer._set_react_version("18.2.0") 

# Create the app
app = Dash(__name__, meta_tags=[{'name': 'viewport', 'content': 'width=device-width, initial-scale=1.0'}]) # Enables mobile responsive app, see: https://www.youtube.com/watch?v=4nEYCGsyz20
server = app.server

# Password protect the app
auth = dash_auth.BasicAuth(app, {
    DASHBOARD_USER : DASHBOARD_PW
})

# Fetch Data
from operations_data import fetch_clean_data
df_clean = fetch_clean_data()

# Create components
title = dmc.Title('Skyroots Dashboard', order=1, ta='center', my='lg') 
rev_graph = dcc.Graph(figure={})
rev_radio = dmc.RadioGroup(
    dmc.Group(
        [dmc.Radio(label='Pro Sorte', value='sorte'), 
        dmc.Radio(label='Pro Kunde', value='kunde')]),
    value='sorte', 
    label='Kategorisierung', 
    size='lg'
    )

# Create the layout
app.layout = dmc.MantineProvider([
        title,
        dmc.Paper(rev_graph, shadow='sm', mx='xl'), 
        dmc.Center(rev_radio, mt='lg')])

# Callback
@app.callback(
    Output(rev_graph, 'figure'),
    Input(rev_radio, 'value')
)

def update_rev(selection):

    button_mapping = {
        'sorte':{
            'column':'green_type',
            'legend':'Sorte'
            },  
        'kunde':{
            'column':'customer_name',
            'legend':'Kunde'
        }
    }

    params = button_mapping[selection]

    fig = px.histogram(
            df_clean, 
            x='invoice_month', 
            y='price_net_total', 
            color = params['column'],
            color_discrete_map = {
                'not greens': px.colors.qualitative.Plotly[1], # Froce 'not greens' to be red
                }
            )

    fig = fig.update_layout(
        title = {
        'text': 'Netto Umsatz pro Monat<br><sup>In EUR<sup><br>'}, 
        #'x':0.5}, # Place title in middle of figure horizontally
        template='plotly_white', 
        yaxis={'title':'EUR'},
        xaxis={'title':'Monat'}, 
        bargap=0.2, 
        legend_title_text=params['legend']
        )

    return fig

if __name__ == '__main__':
    app.run(debug=False)