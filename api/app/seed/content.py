"""The demo marketplace (R2, B1): fictional films, cinemas and people, photographed with CC
photos (credits in web/public/img/CREDITS.md).

- 8 films in the shared catalogue (7 now showing, 1 coming soon);
- 3 verified cinema businesses in Bengaluru (Orbit Cinemas is the demo owner's), plus one new
  business waiting for approval and two open film requests, so the staff queues aren't empty;
- open-ended weekly schedules for every seeded screen: shows materialise lazily 14 days ahead
  for ever (no cron), each with a believable share of seats already sold.

Times are IST wall-clock. The seed checks that no two schedules on one screen can overlap.
"""

from dataclasses import dataclass, field
from datetime import time

from app.schemas.layouts import GridKnobs, Knobs, StallsBalconyKnobs, TierBand

DEMO_CUSTOMER = "customer@frontrow.demo"
DEMO_OWNER = "owner@frontrow.demo"
DEMO_STAFF = "staff@frontrow.demo"
BOOKER_COUNT = 24

BOOKER_NAMES = [
    "Ananya Iyer", "Rohan Mehta", "Priya Nair", "Karthik Rao", "Sneha Reddy", "Arjun Shetty",
    "Divya Krishnan", "Nikhil Bhat", "Meera Pillai", "Aditya Kulkarni", "Shruti Hegde",
    "Varun Menon", "Pooja Deshpande", "Siddharth Jain", "Kavya Gowda", "Rahul Verma",
    "Ishita Sen", "Manoj Prabhu", "Tanvi Shah", "Vikram Das", "Neha Joshi", "Sanjay Patil",
    "Ritu Agarwal", "Abhishek Roy",
]  # fmt: skip

ALL_DAYS = (0, 1, 2, 3, 4, 5, 6)
WEEKEND = (4, 5, 6)  # Fri–Sun
WEEKDAYS = (0, 1, 2, 3)


@dataclass(frozen=True)
class FilmSpec:
    slug: str
    title: str
    synopsis: str
    cast_crew: list[dict[str, str]]
    runtime_min: int
    cert: str
    genres: list[str]
    languages: list[str]
    formats: list[str]
    poster: str
    status: str = "now_showing"
    released_days_ago: int = 10  # negative = releases in the future
    trailer_url: str | None = None


def _cast(director: str, *actors: str) -> list[dict[str, str]]:
    return [{"name": director, "role": "Director"}] + [{"name": a, "role": "Actor"} for a in actors]


FILMS = [
    FilmSpec(
        slug="neon-alley",
        title="Neon Alley",
        synopsis=(
            "A night-shift food-delivery rider in Bengaluru's old market lanes finds a phone "
            "that keeps ringing with the same address. By sunrise he has seen a robbery that "
            "hasn't happened yet — and has six hours to stop it without being blamed for it."
        ),
        cast_crew=_cast("Farah Qureshi", "Arjun Malhotra", "Sana Pillai", "Devraj Kulkarni"),
        runtime_min=128,
        cert="UA",
        genres=["Thriller", "Crime"],
        languages=["Hindi", "English"],
        formats=["2D", "IMAX"],
        poster="neon-alley",
        released_days_ago=9,
    ),  # fmt: skip
    FilmSpec(
        slug="the-last-dune",
        title="The Last Dune",
        synopsis=(
            "Three estranged siblings cross the Thar on camelback to scatter their father's "
            "ashes at a dune that, according to his maps, moves forty metres a year. A sweeping "
            "desert adventure about the places we can't go back to."
        ),
        cast_crew=_cast("Imran Sethi", "Nikita Rao", "Kabir Dsouza", "Lata Menon"),
        runtime_min=152,
        cert="UA",
        genres=["Adventure", "Drama"],
        languages=["English", "Hindi"],
        formats=["2D", "3D", "IMAX"],
        poster="the-last-dune",
        released_days_ago=16,
    ),  # fmt: skip
    FilmSpec(
        slug="undertow",
        title="Undertow",
        synopsis=(
            "A marine archaeologist returns to the sunken temple off the Karwar coast where her "
            "diving partner vanished. The tide tables say the cave is dry for nine minutes a day. "
            "Something down there has been counting too."
        ),
        cast_crew=_cast("Ravi Chandran", "Meera Iyer", "Joseph Mathew"),
        runtime_min=112,
        cert="A",
        genres=["Horror", "Mystery"],
        languages=["English"],
        formats=["2D"],
        poster="undertow",
        released_days_ago=4,
    ),  # fmt: skip
    FilmSpec(
        slug="hollowmere",
        title="Hollowmere",
        synopsis=(
            "In a Western Ghats village where the mist never lifts, a ten-year-old and her "
            "grandmother's talking lantern go looking for the forest spirit that took the "
            "village's colours. A hand-crafted fantasy for every age."
        ),
        cast_crew=_cast("Shalini Hegde", "Aadya Gowda", "Prakash Rai", "Vani Srinivas"),
        runtime_min=118,
        cert="U",
        genres=["Fantasy", "Family"],
        languages=["Kannada", "English", "Tamil"],
        formats=["2D", "3D"],
        poster="hollowmere",
        released_days_ago=23,
    ),  # fmt: skip
    FilmSpec(
        slug="glass-city",
        title="Glass City",
        synopsis=(
            "An architect who designs the glass towers of Outer Ring Road and a street "
            "photographer who documents what they replace keep meeting at the same traffic "
            "signal. A love story told across one monsoon."
        ),
        cast_crew=_cast("Anand Murthy", "Rakshit Nayak", "Disha Shenoy"),
        runtime_min=136,
        cert="UA",
        genres=["Romance", "Drama"],
        languages=["Kannada", "Hindi"],
        formats=["2D"],
        poster="glass-city",
        released_days_ago=6,
    ),  # fmt: skip
    FilmSpec(
        slug="midnight-brass",
        title="Midnight Brass",
        synopsis=(
            "The last brass band of a Goan wedding circuit gets one shot at a national "
            "competition — if its ageing trumpeter can make peace with the son who left to play "
            "jazz in Mumbai. Big tunes, bigger arguments."
        ),
        cast_crew=_cast("Maria Fernandes", "Victor Dsilva", "Neil Pereira", "Asha Kamat"),
        runtime_min=124,
        cert="UA",
        genres=["Music", "Drama"],
        languages=["English", "Hindi"],
        formats=["2D"],
        poster="midnight-brass",
        released_days_ago=30,
    ),  # fmt: skip
    FilmSpec(
        slug="static-bloom",
        title="Static Bloom",
        synopsis=(
            "A radio jockey with three days left on her contract fakes a citywide flower "
            "shortage to save her late-night show. Bengaluru believes her. A comedy about what "
            "a city will do for a good story."
        ),
        cast_crew=_cast("Vinay Bhat", "Pooja Srikanth", "Chikkanna Gowda"),
        runtime_min=109,
        cert="U",
        genres=["Comedy"],
        languages=["Kannada", "Telugu"],
        formats=["2D"],
        poster="static-bloom",
        released_days_ago=2,
    ),  # fmt: skip
    FilmSpec(
        slug="the-rhythm-collective",
        title="The Rhythm Collective",
        synopsis=(
            "Six session musicians who played on every hit of the 90s, never credited, reunite "
            "for one concert under their own name. A music comedy with a soundtrack worth the "
            "ticket on its own."
        ),
        cast_crew=_cast("Sameer Khanna", "Rohit Sen", "Ira Bhattacharya", "Danny Rodrigues"),
        runtime_min=131,
        cert="UA",
        genres=["Music", "Comedy"],
        languages=["Hindi"],
        formats=["2D"],
        poster="rhythm-collective",
        status="coming_soon",
        released_days_ago=-12,
    ),  # fmt: skip
]


@dataclass(frozen=True)
class Slot:
    """One open-ended weekly schedule on a screen."""

    film: str
    language: str
    format: str
    times: tuple[time, ...]
    days: tuple[int, ...] = ALL_DAYS
    fill: float = 0.4  # share of each show already sold (before the soon/weekend factors)


@dataclass(frozen=True)
class ScreenSpec:
    name: str
    formats: list[str]
    knobs: Knobs
    prices: dict[str, int]
    slots: list[Slot] = field(default_factory=list)


@dataclass(frozen=True)
class CinemaSpec:
    name: str
    area: str
    address: str
    facilities: list[str]
    photo: str | None
    screens: list[ScreenSpec]


@dataclass(frozen=True)
class BusinessSpec:
    slug: str
    name: str
    phone: str
    status: str
    owner_email: str
    owner_name: str
    cinemas: list[CinemaSpec]


def _grid(rows: int, seats: int, bands: list[tuple[str, str, int]], aisle: int) -> GridKnobs:
    return GridKnobs(
        rows=rows,
        seats_per_row=seats,
        aisle_after=aisle,
        tiers=[TierBand(key=k, label=label, rows=n) for k, label, n in bands],
    )


T = time
CLASSIC_PRIME_RECLINER = [
    ("classic", "Classic", 6),
    ("prime", "Prime", 6),
    ("recliner", "Recliner", 2),
]

BUSINESSES = [
    BusinessSpec(
        slug="orbit-cinemas",
        name="Orbit Cinemas",
        phone="+91 80 4110 2200",
        status="verified",
        owner_email=DEMO_OWNER,
        owner_name="Kavitha Rao (Orbit Cinemas)",
        cinemas=[
            CinemaSpec(
                name="Orbit Cinemas · Indiranagar",
                area="Indiranagar",
                address="1st floor, 100 Feet Road, HAL 2nd Stage, Indiranagar, Bengaluru 560038",
                facilities=[
                    "Dolby Atmos",
                    "Recliners",
                    "Food court",
                    "Wheelchair access",
                    "M-ticket",
                ],
                photo="orbit-cinemas",
                screens=[
                    ScreenSpec(
                        name="Screen 1",
                        formats=["2D", "3D"],
                        knobs=_grid(14, 18, CLASSIC_PRIME_RECLINER, 9),
                        prices={"classic": 18000, "prime": 26000, "recliner": 45000},
                        slots=[
                            Slot("the-last-dune", "English", "3D", (T(9, 45),), fill=0.25),
                            Slot("neon-alley", "Hindi", "2D", (T(13, 0),), fill=0.4),
                            Slot("the-last-dune", "Hindi", "2D", (T(16, 0),), fill=0.45),
                            Slot("neon-alley", "English", "2D", (T(19, 0),), fill=0.6),
                            Slot("undertow", "English", "2D", (T(22, 0),), fill=0.5),
                        ],
                    ),
                    # Mornings left free so the demo owner can schedule shows here.
                    ScreenSpec(
                        name="Screen 2",
                        formats=["2D"],
                        knobs=_grid(10, 16, [("classic", "Classic", 6), ("prime", "Prime", 4)], 8),
                        prices={"classic": 16000, "prime": 22000},
                        slots=[
                            Slot("glass-city", "Kannada", "2D", (T(17, 30),), fill=0.45),
                            Slot("static-bloom", "Kannada", "2D", (T(20, 30),), fill=0.55),
                        ],
                    ),
                ],
            ),
            CinemaSpec(
                name="Orbit Cinemas · Whitefield",
                area="Whitefield",
                address="Level 3, Phoenix Arc Mall, ITPL Main Road, Whitefield, Bengaluru 560066",
                facilities=["4K laser", "Dolby Atmos", "Recliners", "Parking", "M-ticket"],
                photo=None,
                screens=[
                    ScreenSpec(
                        name="IMAX",
                        formats=["2D", "IMAX"],
                        knobs=_grid(
                            16,
                            22,
                            [
                                ("classic", "Classic", 7),
                                ("prime", "Prime", 7),
                                ("recliner", "Recliner", 2),
                            ],
                            11,
                        ),  # fmt: skip
                        prices={"classic": 32000, "prime": 42000, "recliner": 65000},
                        slots=[
                            Slot(
                                "the-last-dune", "English", "IMAX", (T(10, 0), T(18, 15)), fill=0.5
                            ),
                            Slot("neon-alley", "Hindi", "IMAX", (T(14, 30),), fill=0.35),
                            Slot("neon-alley", "English", "IMAX", (T(21, 45),), fill=0.45),
                        ],
                    ),
                ],
            ),
        ],
    ),
    BusinessSpec(
        slug="cadence-talkies",
        name="Cadence Talkies",
        phone="+91 80 2334 5612",
        status="verified",
        owner_email="manager@cadence-talkies.example",
        owner_name="Raghav Iyengar",
        cinemas=[
            CinemaSpec(
                name="Cadence Talkies",
                area="Malleswaram",
                address="Sampige Road, 8th Cross, Malleswaram, Bengaluru 560003",
                facilities=["Wheelchair access", "Parking"],
                photo="cadence-hall",
                screens=[
                    ScreenSpec(
                        name="Main hall",
                        formats=["2D"],
                        knobs=StallsBalconyKnobs(
                            stalls_rows=12,
                            stalls_seats=28,
                            front_rows=5,
                            balcony_rows=6,
                            balcony_seats=24,
                            curve=0.55,
                        ),  # fmt: skip
                        prices={"front": 12000, "rear": 16000, "balcony": 22000},
                        slots=[
                            Slot("hollowmere", "Kannada", "2D", (T(11, 0),), fill=0.3),
                            Slot("midnight-brass", "English", "2D", (T(14, 15),), fill=0.25),
                            Slot("glass-city", "Kannada", "2D", (T(18, 0),), fill=0.55),
                            Slot("static-bloom", "Kannada", "2D", (T(21, 15),), WEEKEND, 0.5),
                        ],
                    ),
                ],
            ),
        ],
    ),
    BusinessSpec(
        slug="nandi-screens",
        name="Nandi Screens",
        phone="+91 80 4920 7788",
        status="verified",
        owner_email="ops@nandi-screens.example",
        owner_name="Fathima Begum",
        cinemas=[
            CinemaSpec(
                name="Nandi Screens · Koramangala",
                area="Koramangala",
                address="80 Feet Road, 4th Block, Koramangala, Bengaluru 560034",
                facilities=["Dolby Atmos", "Food court", "M-ticket"],
                photo=None,
                screens=[
                    ScreenSpec(
                        name="Audi 1",
                        formats=["2D", "3D"],
                        knobs=_grid(12, 20, [("classic", "Classic", 7), ("prime", "Prime", 5)], 10),
                        prices={"classic": 17000, "prime": 24000},
                        slots=[
                            Slot("hollowmere", "English", "3D", (T(10, 30),), fill=0.3),
                            Slot("hollowmere", "Tamil", "2D", (T(13, 30),), fill=0.25),
                            Slot("midnight-brass", "Hindi", "2D", (T(16, 30),), fill=0.3),
                            Slot("undertow", "English", "2D", (T(19, 30), T(22, 15)), fill=0.45),
                        ],
                    ),
                    ScreenSpec(
                        name="Audi 2",
                        formats=["2D"],
                        knobs=_grid(9, 14, [("classic", "Classic", 6), ("prime", "Prime", 3)], 7),
                        prices={"classic": 15000, "prime": 20000},
                        slots=[
                            Slot("static-bloom", "Telugu", "2D", (T(12, 0), T(15, 0)), fill=0.3),
                            Slot("glass-city", "Hindi", "2D", (T(18, 30),), fill=0.4),
                            Slot("neon-alley", "Hindi", "2D", (T(21, 30),), WEEKEND, 0.6),
                        ],
                    ),
                ],
            ),
        ],
    ),
    # Waiting for approval — fills the staff approvals queue. Their shows go public on approval.
    BusinessSpec(
        slug="lakeview-pictures",
        name="Lakeview Pictures",
        phone="+91 98450 33120",
        status="pending",
        owner_email="rhea@lakeview-pictures.example",
        owner_name="Rhea Kapoor",
        cinemas=[
            CinemaSpec(
                name="Lakeview Pictures · Hebbal",
                area="Hebbal",
                address="Outer Ring Road, near Hebbal Lake, Bengaluru 560024",
                facilities=["Recliners", "Parking"],
                photo=None,
                screens=[
                    ScreenSpec(
                        name="Screen A",
                        formats=["2D"],
                        knobs=_grid(
                            8, 12, [("classic", "Classic", 5), ("recliner", "Recliner", 3)], 6
                        ),
                        prices={"classic": 19000, "recliner": 38000},
                        slots=[
                            Slot("glass-city", "Kannada", "2D", (T(15, 0),), fill=0.0),
                            Slot("the-last-dune", "English", "2D", (T(19, 0),), fill=0.0),
                        ],
                    ),
                ],
            ),
        ],
    ),
]

# Open film requests (business slug, title, note) — the staff "film requests" queue.
FILM_REQUESTS = [
    ("orbit-cinemas", "Kaveri Express", "Kannada road movie, releasing next month — Kannada 2D."),
    ("lakeview-pictures", "Monsoon Letters", "Hindi romance; distributor confirmed 2D prints."),
]

# The demo customer's played booking: (film slug, days ago, IST time, tier, seats) at
# Orbit Indiranagar Screen 2 (free mornings), scanned in at the door.
PAST_BOOKING = ("hollowmere", 3, time(10, 30), "prime", 2)
