import pandas as pd
import folium
from folium.plugins import HeatMap
import requests
import math

# Initialize variables for storing data
latitudes = []
longitudes = []
species_data = {}

# Initial URL for the first page
url = (
    "https://api.inaturalist.org/v1/observations"
    "?place_id=125852&iconic_taxa=Aves&order=desc&order_by=created_at"
    "&quality_grade=research&captive=false&per_page=200"
)

response = requests.get(url)

if response.status_code == 200:
    r = response.json()
    total_results = r["total_results"]
    observations = r["results"]
else:
    print("Failed to fetch data")
    observations = []

# Fetch remaining pages of results
while observations:
    last_id = observations[-1]["id"]
    for observation in observations:
        if (
            "geojson" in observation
            and "coordinates" in observation["geojson"]
            and "photos" in observation
            and observation["photos"]
        ):
            lat = observation["geojson"]["coordinates"][1]
            lon = observation["geojson"]["coordinates"][0]
            species = (
                observation["taxon"]["name"] if "taxon" in observation else "Unknown"
            )
            if species not in species_data:
                species_data[species] = {
                    "latitudes": [],
                    "longitudes": [],
                    "observations": [],
                    "taxon_id": (
                        observation["taxon"]["id"] if "taxon" in observation else ""
                    ),
                }
            species_data[species]["latitudes"].append(lat)
            species_data[species]["longitudes"].append(lon)
            species_data[species]["observations"].append(observation)

            latitudes.append(lat)
            longitudes.append(lon)

    # Check if there are more results
    if len(observations) < 200:
        break

    # Fetch the next page
    url = (
        "https://api.inaturalist.org/v1/observations"
        f"?place_id=125852&iconic_taxa=Aves&order=desc&order_by=created_at"
        f"&quality_grade=research&captive=false&per_page=200&id_below={last_id}"
    )
    response = requests.get(url)

    if response.status_code == 200:
        observations = response.json()["results"]
    else:
        print("Failed to fetch data")
        break


# Function to generate map HTML
def generate_map_html(species, latitudes, longitudes):
    df = pd.DataFrame(
        {"latitude": latitudes, "longitude": longitudes, "count": [1] * len(latitudes)}
    )
    heatmap_data = df[["latitude", "longitude", "count"]].values.tolist()

    if latitudes and longitudes:
        map_center = [
            sum(latitudes) / len(latitudes),
            sum(longitudes) / len(longitudes),
        ]
        bounds = [[min(latitudes), min(longitudes)], [max(latitudes), max(longitudes)]]
    else:
        map_center = [0, 0]
        bounds = [[0, 0], [0, 0]]

    m = folium.Map(location=map_center)
    HeatMap(heatmap_data, radius=30).add_to(m)
    m.fit_bounds(bounds)
    return m._repr_html_()


# Determine pagination parameters
species_list = sorted(species_data.keys())
species_per_page = 10
total_pages = math.ceil(len(species_list) / species_per_page)

# Create HTML content for each page
for page_num in range(total_pages):
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Heatmaps - Página {page_num + 1}</title>
        <style>
            body {{ font-family: Arial, sans-serif; text-align: center; }}
            .map-container {{ margin-bottom: 20px; }}
            .map-title {{ font-size: 1.2em; margin-top: 20px; font-style: italic; }}
            .species-container {{ display: flex; justify-content: center; align-items: center; margin-bottom: 20px; }}
            .species-info {{ margin-left: 20px; text-align: left; }}
            .species-info img {{ max-width: 300px; height: auto; }}
            .subheader {{ font-size: 1em; margin-top: 15px; font-style: normal; }}
            .navbar {{ display: flex; justify-content: center; margin-bottom: 20px; }}
            .navbar select {{ font-size: 1em; padding: 5px; }}
            .bottom-nav {{ display: flex; justify-content: center; margin-top: 20px; }}
            .bottom-nav a {{ margin: 0 5px; text-decoration: none; font-size: 1.2em; padding: 10px 20px; background-color: #007BFF; color: white; border-radius: 5px; }}
            .bottom-nav a:hover {{ background-color: #0056b3; }}
        </style>
        <script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.js"></script>
        <script src="https://cdn.jsdelivr.net/gh/python-visualization/folium@main/folium/templates/leaflet_heat.min.js"></script>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.css"/>
    </head>
    <body>
        <h2>Observações de aves no campus da USP via iNaturalist</h2>
        <div class="navbar">
            <select id="species-select" onchange="navigateToSpecies()">
                <option value="">Selecione uma espécie</option>
    """

    # Add species options to the dropdown
    for i, species in enumerate(species_list):
        species_page = i // species_per_page
        species_anchor = f'#{species.replace(" ", "_")}'
        html_content += f'<option value="heatmaps_page_{species_page + 1}.html{species_anchor}">{species}</option>'

    html_content += """
            </select>
        </div>
    """

    # Add species maps for the current page
    start_idx = page_num * species_per_page
    end_idx = start_idx + species_per_page
    for i, species in enumerate(species_list[start_idx:end_idx], start=start_idx + 1):
        species_info = species_data[species]
        latitudes = species_info["latitudes"]
        longitudes = species_info["longitudes"]

        # Sort observations by date to get the first observation
        species_info["observations"].sort(key=lambda x: x["observed_on"])
        first_observation = species_info["observations"][0]

        # Extract first observation details
        img_url = (
            first_observation["photos"][0]["url"]
            if "photos" in first_observation and first_observation["photos"]
            else ""
        )
        img_url = img_url.replace("square", "medium") if img_url else ""
        license = (
            first_observation["photos"][0]["license_code"]
            if "license_code" in first_observation
            else "N/A"
        )
        observation_url = first_observation["uri"] if "uri" in first_observation else ""
        user_name = (
            first_observation["user"]["login"]
            if "user" in first_observation
            else "Unknown"
        )
        user_profile_url = (
            f"https://www.inaturalist.org/observations?iconic_taxa=Aves&place_id=125852&subview=map&user_id={user_name}"
            if user_name != "Unknown"
            else ""
        )
        observation_date = (
            first_observation["observed_on"]
            if "observed_on" in first_observation
            else "Unknown"
        )
        species_id_url = f"https://www.inaturalist.org/observations?iconic_taxa=Aves&place_id=125852&subview=map&taxon_id={species_info['taxon_id']}"

        species_map_html = generate_map_html(species, latitudes, longitudes)
        species_anchor = species.replace(" ", "_")
        html_content += f"""
        <div class="species-container" id="{species_anchor}">
            <div class="map-container">
                <div class="map-title"><a href="{species_id_url}" target="_blank">{i}. {species}</a></div>
                <div class="subheader">Observações em Nível de Pesquisa: {len(species_info["observations"])}</div>
                <div style="width: 100%; height: 400px;">{species_map_html}</div>
            </div>
            <div class="species-info">
                <a href="{observation_url}" target="_blank">
                    <img src="{img_url}" alt="{species}">
                </a>
                <p><a href="{user_profile_url}" target="_blank">{user_name}</a>, {license} ({observation_date})</p>
            </div>
        </div>
        """

    # Add bottom navigation links
    html_content += '<div class="bottom-nav">'
    if page_num > 0:
        html_content += f'<a href="heatmaps_page_{page_num}.html">Anterior</a>'
    if page_num < total_pages - 1:
        html_content += f'<a href="heatmaps_page_{page_num + 2}.html">Próxima</a>'
    html_content += "</div>"

    html_content += """
    <script>
        function navigateToSpecies() {
            var select = document.getElementById('species-select');
            var page = select.value;
            if (page) {
                window.location.href = page;
            }
        }
    </script>
    </body>
    </html>
    """

    # Save the HTML content to a file
    with open(f"heatmaps_page_{page_num + 1}.html", "w", encoding="utf-8") as f:
        f.write(html_content)

print("Paginated heatmaps saved.")
