import requests
import urllib.parse


class NookipediaClient:
    BASE_URL = "https://api.nookipedia.com"

    def __init__(self, api_key):
        """
        Initialize with your UUID API Key.
        """
        self.headers = {
            "X-API-KEY": api_key,
            "Accept-Version": "1.7.0"
        }

    def _request(self, endpoint, params=None):
        """
        Internal helper to handle requests and error checking.
        """
        if params:
            # Remove None values to avoid sending empty query params
            params = {k: v for k, v in params.items() if v is not None}

        url = f"{self.BASE_URL}{endpoint}"

        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            # Return error dict rather than crashing, for easier handling in Flask
            return {"error": str(e), "status_code": response.status_code}

    # ==========================================
    # General Endpoints
    # ==========================================

    def get_villagers(self, name=None, species=None, personality=None,
                      game=None, birthmonth=None, birthday=None,
                      nhdetails=None, excludedetails=None, thumbsize=None):
        """
        Endpoint: GET /villagers
        Note: 'name' here is a query parameter, not a path parameter.
        """
        return self._request("/villagers", {
            "name": name,
            "species": species,
            "personality": personality,
            "game": game,  # Can be a list/array
            "birthmonth": birthmonth,
            "birthday": birthday,
            "nhdetails": nhdetails,
            "excludedetails": excludedetails,
            "thumbsize": thumbsize
        })

    # ==========================================
    # New Horizons - Critters
    # ==========================================

    def get_fish(self, fish_name=None, month=None, excludedetails=None, thumbsize=None):
        """
        Endpoints:
        - GET /nh/fish (if fish_name is None)
        - GET /nh/fish/{fish} (if fish_name is provided)
        """
        if fish_name:
            return self._request(f"/nh/fish/{urllib.parse.quote(fish_name)}", {"thumbsize": thumbsize})
        return self._request("/nh/fish", {
            "month": month,
            "excludedetails": excludedetails,
            "thumbsize": thumbsize
        })

    def get_bugs(self, bug_name=None, month=None, excludedetails=None, thumbsize=None):
        """
        Endpoints:
        - GET /nh/bugs
        - GET /nh/bugs/{bug}
        """
        if bug_name:
            return self._request(f"/nh/bugs/{urllib.parse.quote(bug_name)}", {"thumbsize": thumbsize})
        return self._request("/nh/bugs", {
            "month": month,
            "excludedetails": excludedetails,
            "thumbsize": thumbsize
        })

    def get_sea_creatures(self, creature_name=None, month=None, excludedetails=None, thumbsize=None):
        """
        Endpoints:
        - GET /nh/sea
        - GET /nh/sea/{sea_creature}
        """
        if creature_name:
            return self._request(f"/nh/sea/{urllib.parse.quote(creature_name)}", {"thumbsize": thumbsize})
        return self._request("/nh/sea", {
            "month": month,
            "excludedetails": excludedetails,
            "thumbsize": thumbsize
        })

    # ==========================================
    # New Horizons - Art & Museum
    # ==========================================

    def get_art(self, artwork_name=None, hasfake=None, excludedetails=None, thumbsize=None):
        """
        Endpoints:
        - GET /nh/art
        - GET /nh/art/{artwork}
        """
        if artwork_name:
            return self._request(f"/nh/art/{urllib.parse.quote(artwork_name)}", {"thumbsize": thumbsize})
        return self._request("/nh/art", {
            "hasfake": hasfake,
            "excludedetails": excludedetails,
            "thumbsize": thumbsize
        })

    def get_fossils_individuals(self, fossil_name=None, thumbsize=None):
        """
        Endpoints:
        - GET /nh/fossils/individuals
        - GET /nh/fossils/individuals/{fossil}
        """
        if fossil_name:
            return self._request(f"/nh/fossils/individuals/{urllib.parse.quote(fossil_name)}", {"thumbsize": thumbsize})
        return self._request("/nh/fossils/individuals", {"thumbsize": thumbsize})

    def get_fossils_groups(self, group_name=None, thumbsize=None):
        """
        Endpoints:
        - GET /nh/fossils/groups
        - GET /nh/fossils/groups/{fossil_group}
        """
        if group_name:
            return self._request(f"/nh/fossils/groups/{urllib.parse.quote(group_name)}", {"thumbsize": thumbsize})
        return self._request("/nh/fossils/groups", {"thumbsize": thumbsize})

    def get_fossils_all(self, name=None, thumbsize=None):
        """
        Endpoints:
        - GET /nh/fossils/all
        - GET /nh/fossils/all/{fossil}
        """
        if name:
            return self._request(f"/nh/fossils/all/{urllib.parse.quote(name)}", {"thumbsize": thumbsize})
        return self._request("/nh/fossils/all", {"thumbsize": thumbsize})

    # ==========================================
    # New Horizons - Items & Customization
    # ==========================================

    def get_furniture(self, furniture_name=None, category=None, color=None, excludedetails=None, thumbsize=None):
        """
        Endpoints:
        - GET /nh/furniture
        - GET /nh/furniture/{furniture}
        """
        if furniture_name:
            return self._request(f"/nh/furniture/{urllib.parse.quote(furniture_name)}", {"thumbsize": thumbsize})
        return self._request("/nh/furniture", {
            "category": category,
            "color": color,  # Can be list
            "excludedetails": excludedetails,
            "thumbsize": thumbsize
        })

    def get_clothing(self, clothing_name=None, category=None, color=None, style=None, labeltheme=None,
                     excludedetails=None, thumbsize=None):
        """
        Endpoints:
        - GET /nh/clothing
        - GET /nh/clothing/{clothing}
        """
        if clothing_name:
            return self._request(f"/nh/clothing/{urllib.parse.quote(clothing_name)}", {"thumbsize": thumbsize})
        return self._request("/nh/clothing", {
            "category": category,
            "color": color,  # Can be list
            "style": style,  # Can be list
            "labeltheme": labeltheme,
            "excludedetails": excludedetails,
            "thumbsize": thumbsize
        })

    def get_interior(self, item_name=None, category=None, color=None, excludedetails=None, thumbsize=None):
        """
        Endpoints:
        - GET /nh/interior
        - GET /nh/interior/{item}
        """
        if item_name:
            return self._request(f"/nh/interior/{urllib.parse.quote(item_name)}", {
                "color": color,
                "thumbsize": thumbsize
            })
        return self._request("/nh/interior", {
            "category": category,
            "color": color,
            "excludedetails": excludedetails,
            "thumbsize": thumbsize
        })

    def get_tools(self, tool_name=None, excludedetails=None, thumbsize=None):
        """
        Endpoints:
        - GET /nh/tools
        - GET /nh/tools/{tool}
        """
        if tool_name:
            return self._request(f"/nh/tools/{urllib.parse.quote(tool_name)}", {"thumbsize": thumbsize})
        return self._request("/nh/tools", {
            "excludedetails": excludedetails,
            "thumbsize": thumbsize
        })

    def get_photos(self, item_name=None, excludedetails=None, thumbsize=None):
        """
        Endpoints:
        - GET /nh/photos
        - GET /nh/photos/{item}
        """
        if item_name:
            return self._request(f"/nh/photos/{urllib.parse.quote(item_name)}", {"thumbsize": thumbsize})
        return self._request("/nh/photos", {
            "excludedetails": excludedetails,
            "thumbsize": thumbsize
        })

    def get_misc_items(self, item_name=None, excludedetails=None, thumbsize=None):
        """
        Endpoints:
        - GET /nh/items
        - GET /nh/items/{item}
        """
        if item_name:
            return self._request(f"/nh/items/{urllib.parse.quote(item_name)}", {"thumbsize": thumbsize})
        return self._request("/nh/items", {
            "excludedetails": excludedetails,
            "thumbsize": thumbsize
        })

    def get_gyroids(self, gyroid_name=None, sound=None, excludedetails=None, thumbsize=None):
        """
        Endpoints:
        - GET /nh/gyroids
        - GET /nh/gyroids/{gyroid}
        """
        if gyroid_name:
            return self._request(f"/nh/gyroids/{urllib.parse.quote(gyroid_name)}", {"thumbsize": thumbsize})
        return self._request("/nh/gyroids", {
            "sound": sound,
            "excludedetails": excludedetails,
            "thumbsize": thumbsize
        })

    # ==========================================
    # New Horizons - Game Data
    # ==========================================

    def get_events(self, date=None, year=None, month=None, day=None):
        """
        Endpoint: GET /nh/events
        """
        return self._request("/nh/events", {
            "date": date,
            "year": year,
            "month": month,
            "day": day
        })

    def get_recipes(self, recipe_name=None, material=None, excludedetails=None, thumbsize=None):
        """
        Endpoints:
        - GET /nh/recipes
        - GET /nh/recipes/{item}
        """
        if recipe_name:
            return self._request(f"/nh/recipes/{urllib.parse.quote(recipe_name)}", {"thumbsize": thumbsize})
        return self._request("/nh/recipes", {
            "material": material,
            "excludedetails": excludedetails,
            "thumbsize": thumbsize
        })

client = NookipediaClient("c8c58fd9-e343-49b2-b9fa-7b8f746c5fa3")
recipes = client.get_recipes()

unique_materials = set()

for recipe in recipes:
    for material in recipe['materials']:
        unique_materials.add(material['name'])

# Convert to a sorted list if you want
unique_materials = sorted(unique_materials)

# Print
for material in unique_materials:
    print(material)