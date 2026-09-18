"""The demo catalogue (PRD decision 2): fictional but plausible, photographed with CC photos.

Four venue rows on three templates (the 2-screen cinema is two grid venues), eight shows, ~20
showtimes over the next 14 days. Photos live in `web/public/img/` (credits there); `poster_url`
is root-relative and served by the web app until v2 moves uploads to Blob.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.schemas.layouts import ArenaKnobs, GridKnobs, Knobs, StallsBalconyKnobs, TierBand

IST = ZoneInfo("Asia/Kolkata")
FEE_PAISE = 3000  # ₹30 convenience fee per ticket (04 §6)

DEMO_PASSWORD = "frontrow-demo"  # public by design — the landing page's demo logins
ORGANISER_EMAIL = "organiser@frontrow.demo"
CUSTOMER_EMAIL = "customer@frontrow.demo"
BOOKER_COUNT = 24  # fictional customers behind the scattered sold seats

BOOKER_NAMES = [
    "Ananya Iyer", "Rohan Mehta", "Priya Nair", "Karthik Rao", "Sneha Reddy", "Arjun Shetty",
    "Divya Krishnan", "Nikhil Bhat", "Meera Pillai", "Aditya Kulkarni", "Shruti Hegde",
    "Varun Menon", "Pooja Deshpande", "Siddharth Jain", "Kavya Gowda", "Rahul Verma",
    "Ishita Sen", "Manoj Prabhu", "Tanvi Shah", "Vikram Das", "Neha Joshi", "Sanjay Patil",
    "Ritu Agarwal", "Abhishek Roy",
]  # fmt: skip


@dataclass(frozen=True)
class VenueSpec:
    key: str
    name: str
    address: str
    photo_url: str
    knobs: Knobs


@dataclass(frozen=True)
class EventSpec:
    slug: str
    title: str
    type: str  # movie | concert
    genre: str
    duration_min: int
    rating: str | None
    synopsis: str
    cast_lineup: list[str]
    poster_url: str
    prices: dict[str, int]  # tier_key → paise, for every venue it plays at
    gallery_urls: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ShowtimeSpec:
    event: str  # event slug
    venue: str  # venue key
    day: int  # days from the seed's day 0
    at: time
    fill: float  # target share of seats sold, 0–1 (never 1: R9 wants a free seat everywhere)


VENUES: list[VenueSpec] = [
    VenueSpec(
        key="orbit-1",
        name="Orbit Cinemas · Screen 1",
        address="100 Feet Road, Indiranagar, Bengaluru 560038",
        photo_url="/img/venues/orbit-cinemas.jpg",
        knobs=GridKnobs(
            rows=13,
            seats_per_row=18,
            aisle_after=9,
            tiers=[
                TierBand(key="classic", label="Classic", rows=5),
                TierBand(key="prime", label="Prime", rows=6),
                TierBand(key="recliner", label="Recliner", rows=2),
            ],
        ),
    ),
    VenueSpec(
        key="orbit-2",
        name="Orbit Cinemas · Screen 2",
        address="100 Feet Road, Indiranagar, Bengaluru 560038",
        photo_url="/img/venues/orbit-cinemas.jpg",
        knobs=GridKnobs(
            rows=10,
            seats_per_row=18,
            aisle_after=9,
            tiers=[
                TierBand(key="classic", label="Classic", rows=4),
                TierBand(key="prime", label="Prime", rows=4),
                TierBand(key="recliner", label="Recliner", rows=2),
            ],
        ),
    ),
    VenueSpec(
        key="cadence",
        name="Cadence Hall",
        address="80 Feet Road, Koramangala 4th Block, Bengaluru 560034",
        photo_url="/img/venues/cadence-hall.jpg",
        knobs=StallsBalconyKnobs(
            stalls_rows=14, stalls_seats=30, front_rows=5, balcony_rows=7, balcony_seats=26
        ),
    ),
    VenueSpec(
        key="yard",
        name="The Yard Arena",
        address="ITPL Main Road, Whitefield, Bengaluru 560066",
        photo_url="/img/venues/yard-arena.jpg",
        knobs=ArenaKnobs(),
    ),
]

CINEMA = {"classic": 22000, "prime": 32000, "recliner": 55000}
HALL = {"front": 150000, "rear": 90000, "balcony": 60000}
ARENA = {"floor": 350000, "gold": 250000, "silver": 150000, "bronze": 90000}

EVENTS: list[EventSpec] = [
    EventSpec(
        slug="neon-alley",
        title="Neon Alley",
        type="movie",
        genre="Thriller",
        duration_min=134,
        rating="UA 16+",
        synopsis=(
            "A night-market courier finds a phone that is not hers and a city that wants it back. "
            "One rain-soaked night in a Bengaluru that never switches off, told in real time."
        ),
        cast_lineup=["Radhika Kamath", "Aarav Bhandari", "Sunil Narayan"],
        poster_url="/img/posters/neon-alley.jpg",
        prices=CINEMA,
    ),
    EventSpec(
        slug="the-last-dune",
        title="The Last Dune",
        type="movie",
        genre="Sci-fi",
        duration_min=141,
        rating="UA",
        synopsis=(
            "The final crew of a terraforming outpost has thirty days of water and a signal from "
            "under the sand. A quiet, widescreen science-fiction epic about what you leave behind."
        ),
        cast_lineup=["Ira Malhotra", "Devendra Kaul", "Zoya Fernandes"],
        poster_url="/img/posters/the-last-dune.jpg",
        prices=CINEMA,
    ),
    EventSpec(
        slug="undertow",
        title="Undertow",
        type="movie",
        genre="Drama",
        duration_min=125,
        rating="UA",
        synopsis=(
            "Two sisters return to the fishing town they left as children to sell their father's "
            "boat. Nobody in town is ready to let it go, least of all them."
        ),
        cast_lineup=["Lakshmi Venkatesh", "Nandita Bose", "Joseph D'Cruz"],
        poster_url="/img/posters/undertow.jpg",
        prices=CINEMA,
    ),
    EventSpec(
        slug="hollowmere",
        title="Hollowmere",
        type="movie",
        genre="Horror",
        duration_min=108,
        rating="A",
        synopsis=(
            "A sound recordist takes a winter job cataloguing birdsong in a forest that has no "
            "birds. Slow-burn folk horror; bring someone to hold on to."
        ),
        cast_lineup=["Tara Subramaniam", "Vivaan Chopra"],
        poster_url="/img/posters/hollowmere.jpg",
        prices=CINEMA,
    ),
    EventSpec(
        slug="glass-city",
        title="Glass City",
        type="movie",
        genre="Crime",
        duration_min=119,
        rating="UA 16+",
        synopsis=(
            "An insurance investigator, a skyscraper with one tenant, and a fire that started on "
            "three floors at once. A glossy, twisting heist thriller set fifty storeys up."
        ),
        cast_lineup=["Kabir Sethi", "Anjali Rathore", "Farhan Qureshi"],
        poster_url="/img/posters/glass-city.jpg",
        prices=CINEMA,
    ),
    EventSpec(
        slug="static-bloom",
        title="Static Bloom",
        type="concert",
        genre="Indie rock",
        duration_min=120,
        rating=None,
        synopsis=(
            "Bengaluru's own four-piece bring the Overgrown tour home: two hours, one encore, and "
            "the light show that made the festival circuit talk. All ages; standing on the floor."
        ),
        cast_lineup=["Static Bloom", "opening: Paper Kites Club"],
        poster_url="/img/posters/static-bloom.jpg",
        prices=ARENA,
    ),
    EventSpec(
        slug="midnight-brass",
        title="Midnight Brass",
        type="concert",
        genre="Jazz",
        duration_min=105,
        rating=None,
        synopsis=(
            "A nine-piece brass ensemble playing late-night standards and originals, unamplified, "
            "in the hall built for it. Doors 7 PM; the bar stays open through the second set."
        ),
        cast_lineup=["Midnight Brass Ensemble", "guest: Nisha Alva (vocals)"],
        poster_url="/img/posters/midnight-brass.jpg",
        prices=HALL,
    ),
    EventSpec(
        slug="rhythm-collective-live",
        title="Rhythm Collective Live",
        type="concert",
        genre="Percussion",
        duration_min=110,
        rating=None,
        synopsis=(
            "Twelve drummers, one stage, no click track. Carnatic rhythm meets West African "
            "percussion in a show that starts in the aisles and ends with the whole hall clapping."
        ),
        cast_lineup=["Rhythm Collective"],
        poster_url="/img/posters/rhythm-collective.jpg",
        prices=HALL,
    ),
]

# ~20 showtimes over 14 days. Day 0 = today in IST, or tomorrow when it is already evening.
SHOWTIMES: list[ShowtimeSpec] = [
    ShowtimeSpec("neon-alley", "orbit-1", 0, time(19, 30), 0.92),  # the "filling fast" one
    ShowtimeSpec("neon-alley", "orbit-1", 1, time(21, 45), 0.61),
    ShowtimeSpec("neon-alley", "orbit-1", 3, time(19, 30), 0.35),
    ShowtimeSpec("neon-alley", "orbit-1", 8, time(19, 30), 0.12),
    ShowtimeSpec("the-last-dune", "orbit-2", 0, time(21, 0), 0.58),
    ShowtimeSpec("the-last-dune", "orbit-2", 2, time(18, 30), 0.44),
    ShowtimeSpec("the-last-dune", "orbit-1", 5, time(21, 0), 0.27),
    ShowtimeSpec("the-last-dune", "orbit-2", 10, time(21, 0), 0.09),
    ShowtimeSpec("undertow", "orbit-2", 1, time(16, 0), 0.31),
    ShowtimeSpec("undertow", "orbit-2", 4, time(19, 0), 0.22),
    ShowtimeSpec("hollowmere", "orbit-1", 2, time(22, 0), 0.48),
    ShowtimeSpec("hollowmere", "orbit-2", 6, time(22, 0), 0.19),
    ShowtimeSpec("glass-city", "orbit-2", 3, time(15, 30), 0.14),
    ShowtimeSpec("glass-city", "orbit-1", 7, time(20, 0), 0.26),
    ShowtimeSpec("static-bloom", "yard", 4, time(20, 0), 0.71),
    ShowtimeSpec("static-bloom", "yard", 11, time(20, 0), 0.38),
    ShowtimeSpec("midnight-brass", "cadence", 2, time(19, 30), 0.66),
    ShowtimeSpec("midnight-brass", "cadence", 9, time(19, 30), 0.29),
    ShowtimeSpec("rhythm-collective-live", "cadence", 6, time(19, 0), 0.53),
    ShowtimeSpec("rhythm-collective-live", "cadence", 13, time(19, 0), 0.17),
]


def day_zero(now: datetime) -> date:
    local = now.astimezone(IST)
    return local.date() + timedelta(days=1 if local.hour >= 17 else 0)


def starts_at(spec: ShowtimeSpec, day0: date) -> datetime:
    return datetime.combine(day0 + timedelta(days=spec.day), spec.at, tzinfo=IST)
