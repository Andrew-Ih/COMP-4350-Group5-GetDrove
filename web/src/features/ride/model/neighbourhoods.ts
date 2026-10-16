import type { LngLat } from "@/shared/map";

/**
 * Rough centres of Winnipeg neighbourhoods, [longitude, latitude]. Display only: they name
 * the rider's chosen area ("Osborne Village"). Searches send the exact point, never a name.
 */
export const NEIGHBOURHOODS: ReadonlyArray<{ name: string; center: LngLat }> = [
  { name: "Osborne Village", center: [-97.144, 49.877] },
  { name: "Wolseley", center: [-97.172, 49.877] },
  { name: "West Broadway", center: [-97.153, 49.883] },
  { name: "Downtown", center: [-97.139, 49.895] },
  { name: "Exchange District", center: [-97.137, 49.9] },
  { name: "West End", center: [-97.17, 49.898] },
  { name: "North End", center: [-97.145, 49.925] },
  { name: "St. Boniface", center: [-97.115, 49.888] },
  { name: "Norwood", center: [-97.118, 49.875] },
  { name: "Crescentwood", center: [-97.158, 49.865] },
  { name: "River Heights", center: [-97.18, 49.86] },
  { name: "Fort Rouge", center: [-97.138, 49.865] },
  { name: "Riverview", center: [-97.133, 49.853] },
  { name: "Lord Roberts", center: [-97.13, 49.846] },
  { name: "St. Vital", center: [-97.111, 49.838] },
  { name: "Southdale", center: [-97.075, 49.845] },
  { name: "River Park South", center: [-97.09, 49.815] },
  { name: "Island Lakes", center: [-97.07, 49.825] },
  { name: "Fort Garry", center: [-97.153, 49.824] },
  { name: "Waverley Heights", center: [-97.17, 49.81] },
  { name: "Fort Richmond", center: [-97.143, 49.795] },
  { name: "St. Norbert", center: [-97.143, 49.768] },
  { name: "Whyte Ridge", center: [-97.215, 49.81] },
  { name: "Bridgwater", center: [-97.195, 49.79] },
  { name: "Linden Woods", center: [-97.205, 49.827] },
  { name: "Tuxedo", center: [-97.22, 49.855] },
  { name: "Charleswood", center: [-97.265, 49.855] },
  { name: "St. James", center: [-97.235, 49.89] },
  { name: "Elmwood", center: [-97.105, 49.915] },
  { name: "East Kildonan", center: [-97.095, 49.93] },
  { name: "Transcona", center: [-97.0, 49.895] },
];
