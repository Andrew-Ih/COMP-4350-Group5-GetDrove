// Generated from contracts/openapi/routing.json by `npm run api:generate`. Do not edit.

export interface paths {
    "/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["health_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/internal/routes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Compute and store a trip's driving route
         * @description Called by Trips when a trip is posted. Computes the driving route, stores it for matching, and returns its distance and duration. Target: under 3 seconds. Calling it again for the same trip replaces the route.
         */
        post: operations["compute_route_internal_routes_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/internal/matches": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Find which trips pass near a rider
         * @description From the candidate trips, returns those whose route passes within walking distance of the rider along the road network (a rider across a river with no nearby crossing doesn't match), with the best pickup point for each. Trips that don't match are left out; an empty list is a normal result.
         */
        post: operations["match_trips_internal_matches_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/trips/{trip_id}/geometry": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * A trip's route for the map
         * @description The route as a GeoJSON LineString. From Sprint 2, riders get the route starting at their pickup point so the driver's start stays private; in Sprint 1 the full route is returned.
         */
        get: operations["route_geometry_trips__trip_id__geometry_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** HealthOut */
        HealthOut: {
            /**
             * Status
             * @constant
             */
            status: "ok";
            /** Service */
            service: string;
        };
        /** InvalidFieldOut */
        InvalidFieldOut: {
            /** Field */
            field: string;
            /** Message */
            message: string;
        };
        /** LineString */
        LineString: {
            /**
             * Type
             * @default LineString
             * @constant
             */
            type: "LineString";
            /**
             * Coordinates
             * @description [lng, lat] pairs (GeoJSON order).
             */
            coordinates: [
                number,
                number
            ][];
        };
        /** Match */
        Match: {
            /**
             * Tripid
             * Format: uuid
             */
            tripId: string;
            /** @description Best point on the route for this rider. */
            pickup: components["schemas"]["Pickup"];
            /**
             * Walkseconds
             * @description Walking time from the rider to the pickup.
             */
            walkSeconds: number;
            /**
             * Riderdistancemeters
             * @description Distance the rider travels in the car (from the pickup to the trip's end).
             */
            riderDistanceMeters: number;
        };
        /** MatchRequest */
        MatchRequest: {
            /** @description The rider's location. Used for matching only, never stored. */
            rider: components["schemas"]["Point"];
            /**
             * Tripids
             * @description Candidate trips Trips has already filtered by time, seats and status.
             */
            tripIds: string[];
        };
        /** MatchResponse */
        MatchResponse: {
            /**
             * Matches
             * @description Only trips whose route passes within walking distance.
             */
            matches: components["schemas"]["Match"][];
        };
        /** Pickup */
        Pickup: {
            /**
             * Label
             * @example Osborne St & River Ave
             */
            label: string;
            /** Lat */
            lat: number;
            /** Lng */
            lng: number;
        };
        /** Point */
        Point: {
            /**
             * Lat
             * @example 49.8794
             */
            lat: number;
            /**
             * Lng
             * @example -97.1663
             */
            lng: number;
        };
        /**
         * Problem
         * @description Every error response (RFC 9457 Problem Details, `application/problem+json`).
         */
        Problem: {
            /**
             * Type
             * @default about:blank
             */
            type: string;
            /** Title */
            title: string;
            /** Status */
            status: number;
            /** Detail */
            detail: string;
            /** Instance */
            instance: string;
            /**
             * Code
             * @description Stable error name.
             * @example routing_engine_unavailable
             */
            code: string;
            /** Requestid */
            requestId?: string | null;
            /** Errors */
            errors?: components["schemas"]["InvalidFieldOut"][] | null;
        };
        /**
         * RouteFeature
         * @description A GeoJSON Feature (RFC 7946), ready for MapLibre.
         */
        RouteFeature: {
            /**
             * Type
             * @default Feature
             * @constant
             */
            type: "Feature";
            geometry: components["schemas"]["LineString"];
            properties: components["schemas"]["RouteProperties"];
        };
        /** RouteProperties */
        RouteProperties: {
            /**
             * Tripid
             * Format: uuid
             */
            tripId: string;
            /** Distancemeters */
            distanceMeters: number;
            /** Durationseconds */
            durationSeconds: number;
        };
        /** RouteRequest */
        RouteRequest: {
            /**
             * Tripid
             * Format: uuid
             */
            tripId: string;
            origin: components["schemas"]["Point"];
            destination: components["schemas"]["Point"];
        };
        /** RouteResponse */
        RouteResponse: {
            /**
             * Tripid
             * Format: uuid
             */
            tripId: string;
            /**
             * Distancemeters
             * @example 9800
             */
            distanceMeters: number;
            /**
             * Durationseconds
             * @example 1320
             */
            durationSeconds: number;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    health_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthOut"];
                };
            };
        };
    };
    compute_route_internal_routes_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RouteRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RouteResponse"];
                };
            };
            /** @description Invalid input; `errors` lists the fields (code `invalid_input`) */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description The routing engine (OSRM) is unavailable or too slow (code `routing_engine_unavailable`) */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    match_trips_internal_matches_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MatchRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MatchResponse"];
                };
            };
            /** @description Invalid input; `errors` lists the fields (code `invalid_input`) */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description The routing engine (OSRM) is unavailable or too slow (code `routing_engine_unavailable`) */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    route_geometry_trips__trip_id__geometry_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                trip_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RouteFeature"];
                };
            };
            /** @description Missing or invalid access token (code `unauthorized`) */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description No route for this trip (code `route_not_found`) */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Invalid input; `errors` lists the fields (code `invalid_input`) */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
}
