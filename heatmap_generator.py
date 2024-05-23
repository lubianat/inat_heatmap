import pandas as pd
import folium
from folium.plugins import HeatMap
import requests

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

# Create HTML content with description and multiple maps
html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Heatmaps</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; }
        .map-container { margin-bottom: 20px; }
        .map-title { font-size: 1.2em; margin-top: 20px; font-style: italic; }
        .species-container { display: flex; justify-content: center; align-items: center; margin-bottom: 20px; }
        .species-info { margin-left: 20px; text-align: left; }
        .species-info img { max-width: 300px; height: auto; }
        .subheader { font-size: 1em; margin-top: 15px; font-style: normal; }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.js"></script>
    <script src="https://cdn.jsdelivr.net/gh/python-visualization/folium@main/folium/templates/leaflet_heat.min.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.css"/>
</head>
<body>
    <h2>Observações de aves no campus da USP via iNaturalist</h2>
"""


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


# Complete heatmap
complete_map_html = generate_map_html("Complete Heatmap", latitudes, longitudes)
html_content += f"""
<div class="species-container">
    <div class="map-container">
        <div class="map-title">Complete Heatmap</div>
        <div style="width: 100%; height: 400px;">{complete_map_html}</div>
    </div>
</div>
"""

# Sort species alphabetically and create individual maps
species_counter = 1
for species in sorted(species_data.keys()):
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
        first_observation["user"]["login"] if "user" in first_observation else "Unknown"
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
    html_content += f"""
    <div class="species-container">
        <div class="map-container">
            <div class="map-title"><a href="{species_id_url}" target="_blank">{species_counter}. {species}</a></div>
            <div class="subheader">Research Grade observations: {len(species_info["observations"])}</div>
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
    species_counter += 1

html_content += """
</body>
</html>
"""

# Save the HTML content to a file
with open("heatmaps_by_species.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("Heatmaps saved as heatmaps_by_species.html")
