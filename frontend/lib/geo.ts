// Asks the browser where the user is. Used by the "Use my location" button.
// Author: Saamarth Attray

export interface Coords {
  lat: number;
  lng: number;
}

export class GeoError extends Error {}

/** Plain-language message for a browser geolocation error code (1 = blocked, 2 = unavailable, 3 = timed out). */
export function geoMessage(code: number): string {
  if (code === 1) return "Location is blocked. Click the lock icon next to the address bar, allow location, then try again.";
  if (code === 3) return "Finding your location took too long. Try again.";
  return "Couldn't work out where you are. Check that location is turned on for this device, then try again.";
}

export function getMyLocation(): Promise<Coords> {
  return new Promise((resolve, reject) => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      reject(new GeoError("This browser can't share your location. Say the city in your request instead, like \"in Austin, TX\"."));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      (err) => reject(new GeoError(geoMessage(err.code))),
      { timeout: 12000, maximumAge: 300000 },
    );
  });
}