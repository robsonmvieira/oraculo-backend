"""Value object for dynamic community classification based on subscribers and growth."""


def classify_size(subscribers: int | None) -> str | None:
    """Classify community size based on subscriber count.

    | Tag     | Range         |
    |---------|---------------|
    | Massive | > 1M          |
    | Huge    | 500k – 1M     |
    | Large   | 100k – 500k   |
    | Medium  | 50k – 100k    |
    | Small   | < 50k         |
    """
    if subscribers is None:
        return None
    if subscribers > 1_000_000:
        return "Massive"
    if subscribers > 500_000:
        return "Huge"
    if subscribers > 100_000:
        return "Large"
    if subscribers > 50_000:
        return "Medium"
    return "Small"


def classify_activity(growth_week: float | None) -> str | None:
    """Classify community activity based on weekly growth percentage.

    | Tag            | Range              |
    |----------------|--------------------|
    | Super Active   | > 0.3% / week      |
    | High Activity  | 0.15% – 0.3%       |
    | Active         | 0.05% – 0.15%      |
    | Moderate       | 0.01% – 0.05%      |
    | Low            | < 0.01%            |
    """
    if growth_week is None:
        return None
    if growth_week > 0.3:
        return "Super Active"
    if growth_week > 0.15:
        return "High Activity"
    if growth_week > 0.05:
        return "Active"
    if growth_week > 0.01:
        return "Moderate"
    return "Low"
