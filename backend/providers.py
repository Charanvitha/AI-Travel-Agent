"""Provider boundaries and a small, named demo catalogue; demo prices are never implied."""

PLACE_CATALOG = {
    "kerala": [
        ("Fort Kochi", "Kochi", "Heritage", 90, "Historic waterfront quarter with colonial-era streets and the Chinese fishing nets."),
        ("Mattancherry Palace", "Kochi", "Museum", 75, "Historic palace museum in Mattancherry; check current opening days."),
        ("Munnar Tea Museum", "Munnar", "Museum", 90, "Tea history and exhibits in the Munnar region."),
        ("Eravikulam National Park", "Munnar", "Nature", 180, "Mountain national park near Munnar; access and seasonal closures vary."),
        ("Alappuzha Backwaters", "Alappuzha", "Waterway", 150, "Canal and lagoon landscape; boat operators and fares vary."),
        ("Kumarakom Bird Sanctuary", "Kumarakom", "Nature", 120, "Bird sanctuary beside Vembanad Lake; seasonal sightings vary."),
        ("Varkala Cliff", "Varkala", "Coast", 90, "Cliffside coastal walk with cafes and sea views."),
        ("Kovalam Beach", "Thiruvananthapuram", "Coast", 90, "A well-known coastal area south of Thiruvananthapuram."),
        ("Edakkal Caves", "Wayanad", "Heritage", 150, "Rock shelters with prehistoric engravings; access includes a climb."),
        ("Wayanad Wildlife Sanctuary", "Wayanad", "Nature", 180, "Protected forest area; safari access and timings need confirmation."),
        ("Periyar Tiger Reserve", "Thekkady", "Nature", 180, "Protected landscape around Periyar Lake; activities are operator-managed."),
        ("Bekal Fort", "Kasaragod", "Heritage", 90, "Coastal fort with views across the Arabian Sea."),
        ("Athirappilly Falls", "Thrissur", "Nature", 120, "Waterfall in Thrissur district; water levels vary by season."),
        ("Thalassery Fort", "Kannur", "Heritage", 75, "Coastal fort in Thalassery, Kannur district."),
        ("Silent Valley National Park", "Palakkad", "Nature", 240, "Protected rainforest reserve; permits and access rules apply."),
    ],
    "hyderabad": [
        ("Charminar", "Hyderabad", "Heritage", 75, "Historic monument in Hyderabad's old city."),
        ("Salar Jung Museum", "Hyderabad", "Museum", 150, "Art and history collections beside the Musi River."),
        ("Golconda Fort", "Hyderabad", "Heritage", 180, "Hilltop fort complex; expect steps and uneven paths."),
        ("Chowmahalla Palace", "Hyderabad", "Heritage", 120, "Former Nizams' palace complex in the old city."),
        ("Nehru Zoological Park", "Hyderabad", "Nature", 240, "Large city zoo; check current visitor and transport information."),
        ("Birla Science Museum", "Hyderabad", "Museum", 150, "Science exhibits and planetarium; separate schedules may apply."),
        ("Hussain Sagar Lake", "Hyderabad", "Outdoor", 90, "Lakefront area with boating options that vary by operator."),
        ("Shilparamam", "Hyderabad", "Culture", 120, "Arts and crafts village in the HITEC City area."),
    ],
    "warangal": [
        ("Warangal Fort", "Warangal", "Heritage", 120, "Kakatiya-era fort ruins and carved stone gateways."),
        ("Thousand Pillar Temple", "Hanamkonda", "Heritage", 90, "Historic temple known for its carved pillars."),
        ("Ramappa Temple", "Palampet", "Heritage", 150, "Kakatiya-era temple and UNESCO-listed World Heritage site."),
        ("Bhadrakali Temple", "Warangal", "Culture", 75, "Temple overlooking Bhadrakali Lake."),
        ("Pakhal Lake", "Warangal district", "Outdoor", 120, "Reservoir and forested setting; facilities vary by season."),
        ("Kakatiya Rock Garden", "Warangal", "Outdoor", 60, "Public garden with sculptures and landscaped grounds."),
        ("Laknavaram Lake", "Mulugu district", "Outdoor", 150, "Lake and suspension bridge area; check local access before travel."),
    ],
    "bengaluru": [
        ("Lalbagh Botanical Garden", "Bengaluru", "Garden", 120, "Historic botanical garden with glasshouse and walking paths."),
        ("Cubbon Park", "Bengaluru", "Garden", 90, "Large central park surrounded by civic and cultural buildings."),
        ("Visvesvaraya Industrial and Technological Museum", "Bengaluru", "Museum", 150, "Interactive science and technology galleries."),
        ("Bangalore Palace", "Bengaluru", "Heritage", 120, "Palace and grounds; entry rules and hours can change."),
        ("Bannerghatta Biological Park", "Bengaluru", "Nature", 240, "Biological park south of the city; safari tickets and availability vary."),
        ("Jawaharlal Nehru Planetarium", "Bengaluru", "Museum", 90, "Astronomy shows and exhibits; showtimes should be checked."),
        ("National Gallery of Modern Art Bengaluru", "Bengaluru", "Gallery", 120, "Modern art gallery in a historic Bengaluru residence."),
    ],
}


class PlacesProvider:
    def search(self, query, destination):
        return demo_places(destination, query)


class WeatherProvider:
    def forecast(self, destination, date=None):
        return {"available": False, "source": "demo", "message": "Forecast unavailable in demo mode."}


class LLMProvider:
    def respond(self, prompt, context=None):
        return "I can help adjust this demo itinerary. Try asking to make it more relaxed or reduce the budget."


def demo_places(destination, query=""):
    place_key = next((key for key in PLACE_CATALOG if key in (destination or "").casefold()), None)
    if not place_key:
        return []
    rows = []
    for name, area, category, duration, description in PLACE_CATALOG[place_key]:
        if query and query.casefold() not in f"{name} {area} {category} {description}".casefold():
            continue
        rows.append({"name": name, "area": area, "category": category, "cost": None, "duration": duration,
                     "description": description, "source": "Named demo recommendation · verify details", "suitability": None})
    return rows
