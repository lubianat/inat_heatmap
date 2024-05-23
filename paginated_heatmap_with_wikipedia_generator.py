import pandas as pd
import folium
from folium.plugins import HeatMap
import requests
import math
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

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


# Function to get the first paragraph from Portuguese Wikipedia
def get_wikipedia_intro(species_name):
    url = f"https://pt.wikipedia.org/api/rest_v1/page/summary/{species_name.replace(' ', '_')}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data.get("extract_html", "Descrição não disponível.")
    return "Descrição não disponível."


# Function to fetch Wikipedia descriptions in parallel
def fetch_wikipedia_descriptions(species_list):
    species_descriptions = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(get_wikipedia_intro, species): species
            for species in species_list
        }
        for future in tqdm(
            futures, total=len(futures), desc="Fetching Wikipedia descriptions"
        ):
            species = futures[future]
            try:
                species_descriptions[species] = future.result()
            except Exception as e:
                species_descriptions[species] = "Descrição não disponível."
                print(f"Error fetching description for {species}: {e}")
    return species_descriptions


# Pre-calculate species descriptions
species_list = sorted(species_data.keys())
print("Fetching Wikipedia descriptions...")
species_descriptions = fetch_wikipedia_descriptions(species_list)

# Determine pagination parameters
species_per_page = 10
total_pages = math.ceil(len(species_list) / species_per_page)

# Get current date
last_update_date = datetime.now().strftime("%Y-%m-%d")

# Create HTML content for each page
print("Generating HTML pages...")
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
            .image-header {{ font-weight: bold; margin-top: 10px; }}
            .image-row {{ display: flex; justify-content: space-around; align-items: center; }}
            .species-description {{ margin-top: 20px; text-align: left; max-width: 800px; margin-left: auto; margin-right: auto; }}
            .footer {{ margin-top: 40px; font-size: 0.9em; color: #555; }}
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

        # Sort observations by date to get the first and most recent observations
        species_info["observations"].sort(key=lambda x: x["observed_on"])
        first_observation = species_info["observations"][0]
        recent_observation = species_info["observations"][-1]

        # Extract observation details
        def extract_observation_details(observation):
            img_url = (
                observation["photos"][0]["url"]
                if "photos" in observation and observation["photos"]
                else ""
            )
            img_url = img_url.replace("square", "medium") if img_url else ""
            license = (
                observation["photos"][0]["license_code"]
                if "license_code" in observation
                else "N/A"
            )
            observation_url = observation["uri"] if "uri" in observation else ""
            user_name = (
                observation["user"]["login"] if "user" in observation else "Unknown"
            )
            user_profile_url = (
                f"https://www.inaturalist.org/observations?iconic_taxa=Aves&place_id=125852&subview=map&user_id={user_name}"
                if user_name != "Unknown"
                else ""
            )
            observation_date = (
                observation["observed_on"]
                if "observed_on" in observation
                else "Unknown"
            )
            return (
                img_url,
                license,
                observation_url,
                user_name,
                user_profile_url,
                observation_date,
            )

        (
            first_img_url,
            first_license,
            first_observation_url,
            first_user_name,
            first_user_profile_url,
            first_observation_date,
        ) = extract_observation_details(first_observation)
        (
            recent_img_url,
            recent_license,
            recent_observation_url,
            recent_user_name,
            recent_user_profile_url,
            recent_observation_date,
        ) = extract_observation_details(recent_observation)

        species_id_url = f"https://www.inaturalist.org/observations?iconic_taxa=Aves&place_id=125852&subview=map&taxon_id={species_info['taxon_id']}"
        species_description = species_descriptions.get(
            species, "Descrição não disponível."
        )
        wikipedia_link = f"https://pt.wikipedia.org/wiki/{species.replace(' ', '_')}"

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
                <div class="image-row">
                    <div>
                        <div class="image-header">Primeira Observação</div>
                        <a href="{first_observation_url}" target="_blank">
                            <img src="{first_img_url}" alt="{species}">
                        </a>
                        <p><a href="{first_user_profile_url}" target="_blank">{first_user_name}</a>, {first_license} ({first_observation_date})</p>
                    </div>
                    <div>
                        <div class="image-header">Observação Mais Recente</div>
                        <a href="{recent_observation_url}" target="_blank">
                            <img src="{recent_img_url}" alt="{species}">
                        </a>
                        <p><a href="{recent_user_profile_url}" target="_blank">{recent_user_name}</a>, {recent_license} ({recent_observation_date})</p>
                    </div>
                </div>
                <div class="species-description">
                    <p>{species_description}</p>
                    <p><a href="{wikipedia_link}" target="_blank">Link para Wikipedia</a></p>
                </div>
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

    # Add footer
    html_content += f"""
    <div class="footer">
        <p>Desenvolvido por Tiago Lubiana</p>
        <p><a href="https://github.com/lubianat/inat_heatmap" target="_blank">Repositório no GitHub</a></p>
        <p>Licença: <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank">CC-BY</a></p>
        <p>Conteúdo da Wikipedia licenciado em <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank">CC-BY-SA</a></p>
        <p>Última atualização: {last_update_date}</p>
    </div>
    """

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

# Create "Sobre o projeto" page
sobre_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Sobre o projeto</title>
    <style>
        body {{ font-family: Arial, sans-serif; text-align: center; margin: 20px; }}
        .content {{ max-width: 800px; margin: auto; text-align: left; }}
        .footer {{ margin-top: 40px; font-size: 0.9em; color: #555; text-align: center; }}
    </style>
</head>
<body>
    <h2>Sobre o projeto</h2>
    <div class="content">
        <p>Este projeto foi desenvolvido por Tiago Lubiana para visualizar as observações de aves no campus da USP utilizando dados do iNaturalist.</p>
        <p>As observações são exibidas em um mapa de calor, juntamente com a primeira e a mais recente observação de cada espécie, bem como uma breve descrição retirada da Wikipedia.</p>
        <p>O código-fonte do projeto está disponível no GitHub: <a href="https://github.com/lubianat/inat_heatmap" target="_blank">Repositório no GitHub</a></p>
    </div>
    <div class="footer">
        <p>Licença: <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank">CC-BY</a></p>
        <p>Conteúdo da Wikipedia licenciado em <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank">CC-BY-SA</a></p>
        <p>Última atualização: {last_update_date}</p>
    </div>
</body>
</html>
"""

with open("sobre_o_projeto.html", "w", encoding="utf-8") as f:
    f.write(sobre_content)

# Create README in Portuguese
readme_content = f"""
# Visualização de Observações de Aves na USP

Este projeto foi desenvolvido por Tiago Lubiana para visualizar as observações de aves no campus da USP utilizando dados do iNaturalist.

## Sobre o projeto

As observações são exibidas em um mapa de calor, juntamente com a primeira e a mais recente observação de cada espécie, bem como uma breve descrição retirada da Wikipedia.

## Licença

O código-fonte deste projeto está licenciado sob a licença [CC-BY](https://creativecommons.org/licenses/by/4.0/).

O conteúdo da Wikipedia está licenciado sob a licença [CC-BY-SA](https://creativecommons.org/licenses/by-sa/4.0/).

## Última atualização

{last_update_date}
"""

with open("README.md", "w", encoding="utf-8") as f:
    f.write(readme_content)

print("Sobre o projeto e README gerados.")
import pandas as pd
import folium
from folium.plugins import HeatMap
import requests
import math
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

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


# Function to get the first paragraph from Portuguese Wikipedia
def get_wikipedia_intro(species_name):
    url = f"https://pt.wikipedia.org/api/rest_v1/page/summary/{species_name.replace(' ', '_')}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data.get("extract_html", "Descrição não disponível.")
    return "Descrição não disponível."


# Function to fetch Wikipedia descriptions in parallel
def fetch_wikipedia_descriptions(species_list):
    species_descriptions = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(get_wikipedia_intro, species): species
            for species in species_list
        }
        for future in tqdm(
            futures, total=len(futures), desc="Fetching Wikipedia descriptions"
        ):
            species = futures[future]
            try:
                species_descriptions[species] = future.result()
            except Exception as e:
                species_descriptions[species] = "Descrição não disponível."
                print(f"Error fetching description for {species}: {e}")
    return species_descriptions


# Pre-calculate species descriptions
species_list = sorted(species_data.keys())
print("Fetching Wikipedia descriptions...")
species_descriptions = fetch_wikipedia_descriptions(species_list)

# Determine pagination parameters
species_per_page = 10
total_pages = math.ceil(len(species_list) / species_per_page)

# Get current date
last_update_date = datetime.now().strftime("%Y-%m-%d")

# Create HTML content for each page
print("Generating HTML pages...")
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
            .image-header {{ font-weight: bold; margin-top: 10px; }}
            .image-row {{ display: flex; justify-content: space-around; align-items: center; }}
            .species-description {{ margin-top: 20px; text-align: left; max-width: 800px; margin-left: auto; margin-right: auto; }}
            .footer {{ margin-top: 40px; font-size: 0.9em; color: #555; }}
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

        # Sort observations by date to get the first and most recent observations
        species_info["observations"].sort(key=lambda x: x["observed_on"])
        first_observation = species_info["observations"][0]
        recent_observation = species_info["observations"][-1]

        # Extract observation details
        def extract_observation_details(observation):
            img_url = (
                observation["photos"][0]["url"]
                if "photos" in observation and observation["photos"]
                else ""
            )
            img_url = img_url.replace("square", "medium") if img_url else ""
            license = (
                observation["photos"][0]["license_code"]
                if "license_code" in observation
                else "N/A"
            )
            observation_url = observation["uri"] if "uri" in observation else ""
            user_name = (
                observation["user"]["login"] if "user" in observation else "Unknown"
            )
            user_profile_url = (
                f"https://www.inaturalist.org/observations?iconic_taxa=Aves&place_id=125852&subview=map&user_id={user_name}"
                if user_name != "Unknown"
                else ""
            )
            observation_date = (
                observation["observed_on"]
                if "observed_on" in observation
                else "Unknown"
            )
            return (
                img_url,
                license,
                observation_url,
                user_name,
                user_profile_url,
                observation_date,
            )

        (
            first_img_url,
            first_license,
            first_observation_url,
            first_user_name,
            first_user_profile_url,
            first_observation_date,
        ) = extract_observation_details(first_observation)
        (
            recent_img_url,
            recent_license,
            recent_observation_url,
            recent_user_name,
            recent_user_profile_url,
            recent_observation_date,
        ) = extract_observation_details(recent_observation)

        species_id_url = f"https://www.inaturalist.org/observations?iconic_taxa=Aves&place_id=125852&subview=map&taxon_id={species_info['taxon_id']}"
        species_description = species_descriptions.get(
            species, "Descrição não disponível."
        )
        wikipedia_link = f"https://pt.wikipedia.org/wiki/{species.replace(' ', '_')}"

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
                <div class="image-row">
                    <div>
                        <div class="image-header">Primeira Observação</div>
                        <a href="{first_observation_url}" target="_blank">
                            <img src="{first_img_url}" alt="{species}">
                        </a>
                        <p><a href="{first_user_profile_url}" target="_blank">{first_user_name}</a>, {first_license} ({first_observation_date})</p>
                    </div>
                    <div>
                        <div class="image-header">Observação Mais Recente</div>
                        <a href="{recent_observation_url}" target="_blank">
                            <img src="{recent_img_url}" alt="{species}">
                        </a>
                        <p><a href="{recent_user_profile_url}" target="_blank">{recent_user_name}</a>, {recent_license} ({recent_observation_date})</p>
                    </div>
                </div>
                <div class="species-description">
                    <p>{species_description}</p>
                    <p><a href="{wikipedia_link}" target="_blank">Link para Wikipedia</a></p>
                </div>
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

    # Add footer
    html_content += f"""
    <div class="footer">
        <p>Desenvolvido com ♥ por Tiago Lubiana.</p>
        <p><a href="https://github.com/lubianat/inat_heatmap" target="_blank">Repositório no GitHub</a></p>
        <p>Conteúdo da Wikipedia licenciado em <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank">CC-BY-SA</a></p>
        <p>Última atualização: {last_update_date}</p>
    </div>
    """

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
