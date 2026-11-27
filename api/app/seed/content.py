"""The demo marketplace (R2, B1): real films in Indian cinemas from late November 2026 to
January 2027, playing at fictional Bengaluru cinemas run by fictional people.

- 11 real films (7 Hindi, 4 Hollywood with their Indian dubs). Title, Indian release date, CBFC
  certificate, runtime, languages, director and cast are as published (sources in the PR "Real
  Bollywood + Hollywood catalogue"); `cert=None` means not yet certified and `runtime_min=None`
  not yet announced. Synopses are our own one-liners; posters are original typographic art
  (web/public/img/posters/*.png, drawn by api/scripts/make_posters.py) — no studio artwork;
- 3 verified cinema businesses in Bengaluru (Orbit Cinemas is the demo owner's), plus one new
  business waiting for approval and two open film requests, so the staff queues aren't empty;
- open-ended weekly schedules for every seeded screen: shows materialise lazily 14 days ahead
  for ever (no cron), each with a believable share of seats already sold. A coming-soon film's
  schedules start on its release date, and the film turns "now showing" that day.

Times are IST wall-clock. The seed checks that no two schedules on one screen can overlap.
"""

from dataclasses import dataclass, field
from datetime import date, time

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
    runtime_min: int | None  # None: not announced (shows are planned at PLANNING_RUNTIME_MIN)
    cert: str | None  # CBFC: U, UA 7+, UA 13+, UA 16+ or A; None: not yet certified
    genres: list[str]
    languages: list[str]
    formats: list[str]
    poster: str
    release: date  # the Indian theatrical release date

    def status(self, today: date) -> str:
        return "now_showing" if self.release <= today else "coming_soon"


def _cast(directors: str | tuple[str, ...], *actors: str) -> list[dict[str, str]]:
    names = (directors,) if isinstance(directors, str) else directors
    return [{"name": d, "role": "Director"} for d in names] + [
        {"name": a, "role": "Actor"} for a in actors
    ]


FILMS = [
    # --- Hindi ------------------------------------------------------------------------------------
    FilmSpec(
        slug="ramayana-part-1",
        title="Ramayana: Part 1",
        synopsis=(
            "The first half of the epic: Prince Rama's exile from Ayodhya with Sita and "
            "Lakshmana, and the events that set him on a collision course with Ravana, the "
            "king of Lanka."
        ),
        cast_crew=_cast("Nitesh Tiwari", "Ranbir Kapoor", "Yash", "Sai Pallavi", "Sunny Deol"),
        runtime_min=195,
        cert="U",
        genres=["Mythology", "Action", "Drama"],
        languages=["Hindi", "Tamil", "Telugu", "Kannada", "Malayalam"],
        formats=["2D"],
        poster="ramayana-part-1",
        release=date(2026, 11, 5),
    ),  # fmt: skip
    FilmSpec(
        slug="yeh-prem-mol-liya",
        title="Yeh Prem Mol Liya",
        synopsis=(
            "Sooraj Barjatya's romantic family drama, in which a young couple's love story "
            "plays out among the elders and relatives of two close-knit families."
        ),
        cast_crew=_cast(
            "Sooraj Barjatya",
            "Ayushmann Khurrana",
            "Sharvari",
            "Anupam Kher",
            "Supriya Pathak",
        ),
        runtime_min=173,
        cert="UA 13+",
        genres=["Romance", "Family", "Drama"],
        languages=["Hindi"],
        formats=["2D"],
        poster="yeh-prem-mol-liya",
        release=date(2026, 11, 27),
    ),  # fmt: skip
    FilmSpec(
        slug="maatrubhumi",
        title="Maatrubhumi: May War Rest in Peace",
        synopsis=(
            "A war drama drawn from the 2020 clashes in the Galwan Valley, following the "
            "Indian soldiers holding a remote post on the Ladakh frontier."
        ),
        cast_crew=_cast(
            "Apoorva Lakhia",
            "Salman Khan",
            "Chitrangada Singh",
            "Ankur Bhatia",
            "Zeyn Shaw",
        ),
        runtime_min=154,
        cert="UA 16+",
        genres=["War", "Drama"],
        languages=["Hindi"],
        formats=["2D"],
        poster="maatrubhumi",
        release=date(2026, 12, 4),
    ),  # fmt: skip
    FilmSpec(
        slug="eetha",
        title="Eetha",
        synopsis=(
            "A drama inspired by the life of Vithabai Narayangaonkar, the celebrated Tamasha "
            "and Lavani performer of Maharashtra."
        ),
        cast_crew=_cast(
            "Laxman Utekar",
            "Shraddha Kapoor",
            "Randeep Hooda",
            "Mohammed Zeeshan Ayyub",
            "Siddharth Jadhav",
        ),
        runtime_min=None,
        cert=None,
        genres=["Biopic", "Musical", "Drama"],
        languages=["Hindi"],
        formats=["2D"],
        poster="eetha",
        release=date(2026, 12, 4),
    ),  # fmt: skip
    FilmSpec(
        slug="king",
        title="King",
        synopsis=(
            "Siddharth Anand's action thriller, with Shah Rukh Khan leading an ensemble that "
            "includes Suhana Khan, Deepika Padukone and Abhishek Bachchan."
        ),
        cast_crew=_cast(
            "Siddharth Anand",
            "Shah Rukh Khan",
            "Suhana Khan",
            "Deepika Padukone",
            "Abhishek Bachchan",
        ),
        runtime_min=None,
        cert=None,
        genres=["Action", "Thriller"],
        languages=["Hindi"],
        formats=["2D"],
        poster="king",
        release=date(2026, 12, 24),
    ),  # fmt: skip
    FilmSpec(
        slug="golmaal-5",
        title="Golmaal 5",
        synopsis=(
            "The fifth instalment of Rohit Shetty's Golmaal comedy series, bringing the old "
            "gang back together for another round of mix-ups."
        ),
        cast_crew=_cast(
            "Rohit Shetty",
            "Ajay Devgn",
            "Akshay Kumar",
            "Arshad Warsi",
            "Tusshar Kapoor",
        ),
        runtime_min=None,
        cert=None,
        genres=["Comedy"],
        languages=["Hindi"],
        formats=["2D"],
        poster="golmaal-5",
        release=date(2027, 1, 8),
    ),  # fmt: skip
    FilmSpec(
        slug="love-and-war",
        title="Love & War",
        synopsis=(
            "Sanjay Leela Bhansali's romantic drama, with Ranbir Kapoor, Alia Bhatt and Vicky "
            "Kaushal in the lead roles."
        ),
        cast_crew=_cast("Sanjay Leela Bhansali", "Ranbir Kapoor", "Alia Bhatt", "Vicky Kaushal"),
        runtime_min=None,
        cert=None,
        genres=["Romance", "Drama"],
        languages=["Hindi", "Tamil", "Telugu"],
        formats=["2D"],
        poster="love-and-war",
        release=date(2027, 1, 21),
    ),  # fmt: skip
    # --- Hollywood --------------------------------------------------------------------------------
    FilmSpec(
        slug="hunger-games-sunrise-on-the-reaping",
        title="The Hunger Games: Sunrise on the Reaping",
        synopsis=(
            "A prequel set decades before the original series: in the year of the Second "
            "Quarter Quell, a young Haymitch Abernathy of District 12 is reaped for the Games."
        ),
        cast_crew=_cast(
            "Francis Lawrence",
            "Joseph Zada",
            "Jesse Plemons",
            "Ralph Fiennes",
            "Elle Fanning",
        ),
        runtime_min=158,
        cert="UA 16+",
        genres=["Action", "Sci-Fi", "Thriller"],
        languages=["English"],
        formats=["2D"],
        poster="hunger-games-sunrise-on-the-reaping",
        release=date(2026, 11, 20),
    ),  # fmt: skip
    FilmSpec(
        slug="how-to-rob-a-bank",
        title="How to Rob a Bank",
        synopsis="David Leitch's action comedy about a bank heist that refuses to go to plan.",
        cast_crew=_cast(
            "David Leitch",
            "Nicholas Hoult",
            "Zoë Kravitz",
            "Anna Sawai",
            "Rhenzy Feliz",
        ),
        runtime_min=122,
        cert="A",
        genres=["Action", "Comedy", "Crime"],
        languages=["English"],
        formats=["2D"],
        poster="how-to-rob-a-bank",
        release=date(2026, 11, 20),
    ),  # fmt: skip
    FilmSpec(
        slug="avengers-doomsday",
        title="Avengers: Doomsday",
        synopsis=(
            "The Avengers and their allies regroup to face Doctor Doom in the next chapter of "
            "Marvel's multiverse saga."
        ),
        cast_crew=_cast(
            ("Anthony Russo", "Joe Russo"),
            "Robert Downey Jr.",
            "Chris Evans",
            "Chris Hemsworth",
            "Pedro Pascal",
        ),
        runtime_min=150,
        cert=None,
        genres=["Superhero", "Action", "Sci-Fi"],
        languages=["English", "Hindi", "Tamil", "Telugu"],
        formats=["2D", "3D"],
        poster="avengers-doomsday",
        release=date(2026, 12, 17),
    ),  # fmt: skip
    FilmSpec(
        slug="dune-part-three",
        title="Dune: Part Three",
        synopsis=(
            "The close of Denis Villeneuve's trilogy, adapted from Frank Herbert's Dune "
            "Messiah: years into Paul Atreides' reign, the holy war fought in his name has "
            "spread far beyond Arrakis."
        ),
        cast_crew=_cast(
            "Denis Villeneuve",
            "Timothée Chalamet",
            "Zendaya",
            "Jason Momoa",
            "Florence Pugh",
        ),
        runtime_min=150,
        cert=None,
        genres=["Sci-Fi", "Adventure", "Drama"],
        languages=["English", "Hindi"],
        formats=["2D", "IMAX"],
        poster="dune-part-three",
        release=date(2026, 12, 18),
    ),  # fmt: skip
]

# The fictional films of the first demo catalogue. A reseed retires them: their schedules and
# every show no real visitor has booked are deleted; a film someone still holds a ticket for
# stays, marked ended, so that ticket keeps working.
RETIRED_FILMS = (
    "neon-alley", "the-last-dune", "undertow", "hollowmere", "glass-city", "midnight-brass",
    "static-bloom", "the-rhythm-collective",
)  # fmt: skip
# Open requests the first seed made for fictional titles; a reseed removes them.
RETIRED_REQUESTS = ("Kaveri Express", "Monsoon Letters")


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

RAMAYANA = "ramayana-part-1"
YPML = "yeh-prem-mol-liya"
HUNGER_GAMES = "hunger-games-sunrise-on-the-reaping"
ROB_A_BANK = "how-to-rob-a-bank"
AVENGERS = "avengers-doomsday"
DUNE = "dune-part-three"

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
                            Slot(RAMAYANA, "Hindi", "2D", (T(9, 30),), fill=0.35),
                            Slot(YPML, "Hindi", "2D", (T(13, 15),), fill=0.5),
                            Slot(AVENGERS, "English", "3D", (T(16, 30),), fill=0.6),
                            Slot(RAMAYANA, "Hindi", "2D", (T(19, 30),), fill=0.6),
                        ],
                    ),
                    # Mornings left free so the demo owner can schedule shows here.
                    ScreenSpec(
                        name="Screen 2",
                        formats=["2D"],
                        knobs=_grid(10, 16, [("classic", "Classic", 6), ("prime", "Prime", 4)], 8),
                        prices={"classic": 16000, "prime": 22000},
                        slots=[
                            Slot(ROB_A_BANK, "English", "2D", (T(17, 30),), fill=0.45),
                            Slot(HUNGER_GAMES, "English", "2D", (T(20, 0),), fill=0.5),
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
                            Slot(RAMAYANA, "Hindi", "2D", (T(9, 30),), fill=0.3),
                            Slot(DUNE, "English", "IMAX", (T(13, 15), T(19, 30)), fill=0.55),
                            Slot(HUNGER_GAMES, "English", "2D", (T(16, 15),), fill=0.35),
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
                            Slot(RAMAYANA, "Kannada", "2D", (T(10, 0),), fill=0.4),
                            Slot(YPML, "Hindi", "2D", (T(13, 45),), fill=0.35),
                            Slot("maatrubhumi", "Hindi", "2D", (T(17, 15),), fill=0.55),
                            Slot("king", "Hindi", "2D", (T(20, 15),), fill=0.7),
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
                            Slot(AVENGERS, "Hindi", "3D", (T(10, 0),), fill=0.5),
                            Slot(RAMAYANA, "Tamil", "2D", (T(13, 0),), fill=0.3),
                            Slot("eetha", "Hindi", "2D", (T(16, 45),), fill=0.4),
                            Slot(ROB_A_BANK, "English", "2D", (T(20, 15),), fill=0.45),
                        ],
                    ),
                    ScreenSpec(
                        name="Audi 2",
                        formats=["2D"],
                        knobs=_grid(9, 14, [("classic", "Classic", 6), ("prime", "Prime", 3)], 7),
                        prices={"classic": 15000, "prime": 20000},
                        slots=[
                            Slot(RAMAYANA, "Telugu", "2D", (T(11, 0),), fill=0.3),
                            Slot("golmaal-5", "Hindi", "2D", (T(14, 45),), fill=0.5),
                            Slot("love-and-war", "Hindi", "2D", (T(18, 15),), fill=0.55),
                            Slot("maatrubhumi", "Hindi", "2D", (T(21, 30),), WEEKEND, 0.6),
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
                            Slot(YPML, "Hindi", "2D", (T(15, 0),), fill=0.0),
                            Slot(HUNGER_GAMES, "English", "2D", (T(19, 0),), fill=0.0),
                        ],
                    ),
                ],
            ),
        ],
    ),
]

# Open film requests (business slug, title, note) — the staff "film requests" queue. Both are real
# films the catalogue doesn't carry yet.
FILM_REQUESTS = [
    (
        "orbit-cinemas",
        "Jumanji: Open World",
        "Sony's English, Hindi, Tamil and Telugu versions — Indian date still to be confirmed.",
    ),
    ("lakeview-pictures", "Gunmaaster G9", "Hindi, in cinemas from 27 Nov — evening shows."),
]

# The demo customer's played booking: (film slug, days ago, IST time, tier, seats) at
# Orbit Indiranagar Screen 2 (free mornings), scanned in at the door.
PAST_BOOKING = (RAMAYANA, 3, time(10, 30), "prime", 2)
