"""Geographic tools: Haversine distance, K-Means clustering, nearest-neighbour routing."""

import math
from typing import Optional

from sklearn.cluster import KMeans
from numpy import ndarray

from app.schemas import POI, DayCluster


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate great-circle distance between two points in kilometres.

    Args:
        lat1, lon1: First point latitude and longitude in degrees
        lat2, lon2: Second point latitude and longitude in degrees

    Returns:
        Distance in kilometres as a non-negative float

    Raises:
        ValueError: If any input is non-numeric or out of valid range
    """
    # Validate inputs
    for val in (lat1, lon1, lat2, lon2):
        if not isinstance(val, (int, float)):
            raise ValueError(f"All coordinates must be numeric, got {type(val).__name__}")

    if not (-90 <= lat1 <= 90 and -90 <= lat2 <= 90):
        raise ValueError(f"Latitude must be in [-90, 90], got lat1={lat1}, lat2={lat2}")
    if not (-180 <= lon1 <= 180 and -180 <= lon2 <= 180):
        raise ValueError(f"Longitude must be in [-180, 180], got lon1={lon1}, lon2={lon2}")

    # Haversine formula
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def compute_centroid(pois: list[POI]) -> tuple[float, float]:
    """
    Compute arithmetic mean latitude and longitude of POIs.

    Args:
        pois: Non-empty list of POI objects

    Returns:
        Tuple (mean_lat, mean_lon)
    """
    if not pois:
        raise ValueError("pois list must not be empty")

    mean_lat = sum(p.lat for p in pois) / len(pois)
    mean_lon = sum(p.lon for p in pois) / len(pois)
    return mean_lat, mean_lon


def nearest_neighbour_route(pois: list[POI]) -> list[POI]:
    """
    Order POIs using greedy nearest-neighbour algorithm.

    Starts from the first POI, then repeatedly selects the unvisited POI
    with the smallest Haversine distance from the current position.

    Args:
        pois: Non-empty list of POI objects

    Returns:
        Permutation of input POIs ordered by nearest-neighbour routing
    """
    if not pois:
        raise ValueError("pois list must not be empty")

    unvisited = list(pois)
    ordered = [unvisited.pop(0)]

    while unvisited:
        current = ordered[-1]
        # Find unvisited POI with minimum distance to current
        nearest = min(
            unvisited,
            key=lambda p: haversine(current.lat, current.lon, p.lat, p.lon),
        )
        ordered.append(nearest)
        unvisited.remove(nearest)

    return ordered


def order_cluster_by_haversine(cluster: list[POI]) -> list[POI]:
    """Alias for nearest_neighbour_route."""
    return nearest_neighbour_route(cluster)


def cluster_pois(pois: list[POI], n_clusters: int) -> list[DayCluster]:
    """
    Cluster POIs into daily groups using K-Means and order each by nearest-neighbour.

    Args:
        pois: List of POI objects
        n_clusters: Number of clusters (days)

    Returns:
        List of DayCluster objects with POIs ordered within each cluster

    Raises:
        ValueError: If n_clusters < 1 or len(pois) < n_clusters
    """
    if n_clusters < 1:
        raise ValueError(f"n_clusters must be >= 1, got {n_clusters}")
    if len(pois) < n_clusters:
        raise ValueError(
            f"Number of POIs ({len(pois)}) must be >= n_clusters ({n_clusters})"
        )

    # Extract coordinates
    coords = [[p.lat, p.lon] for p in pois]

    # Run K-Means
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(coords)

    # Group POIs by cluster
    cluster_map = {}
    for idx, label in enumerate(labels):
        if label not in cluster_map:
            cluster_map[label] = []
        cluster_map[label].append(pois[idx])

    # Build DayCluster objects
    result = []
    for day_num, cluster_pois_list in enumerate(sorted(cluster_map.keys())):
        cluster_pois_list = cluster_map[cluster_pois_list]
        ordered = nearest_neighbour_route(cluster_pois_list)
        centroid_lat, centroid_lon = compute_centroid(ordered)
        total_hours = sum(p.estimated_duration_hours for p in ordered)

        result.append(
            DayCluster(
                day_number=day_num + 1,
                pois=ordered,
                centroid_lat=centroid_lat,
                centroid_lon=centroid_lon,
                total_duration_hours=total_hours,
            )
        )

    return result
