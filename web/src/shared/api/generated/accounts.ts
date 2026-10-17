// Generated from contracts/openapi/accounts.json by `npm run api:generate`. Do not edit.

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
    "/auth/signup": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Sign up
         * @description Creates an unverified account and sends a verification email whose link is valid for 24 hours. Publishes the UserRegistered event.
         */
        post: operations["signup_auth_signup_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/verify": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Verify email
         * @description Marks the email as verified using the token from the link.
         */
        post: operations["verify_email_auth_verify_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/resend-verification": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Resend the verification email
         * @description Sends a new link and makes older links stop working. Always returns 202, even for an unknown or already-verified email, so it can't be used to find out who has an account.
         */
        post: operations["resend_verification_auth_resend_verification_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Log in
         * @description Returns an access token and sets the `refresh_token` cookie.
         */
        post: operations["login_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/refresh": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Get a new access token
         * @description Uses the `refresh_token` cookie; returns a new access token and replaces the cookie.
         */
        post: operations["refresh_auth_refresh_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Log out
         * @description Ends the session on this device: the refresh token stops working and the cookie is cleared.
         */
        post: operations["logout_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** The logged-in user */
        get: operations["me_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/.well-known/jwks.json": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Public keys for checking access tokens
         * @description Other services fetch this (and cache it) to check access tokens without calling Accounts on every request.
         */
        get: operations["jwks__well_known_jwks_json_get"];
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
            /**
             * Field
             * @example password
             */
            field: string;
            /**
             * Message
             * @example String should have at least 10 characters
             */
            message: string;
        };
        /**
         * Jwk
         * @description One public signing key (RFC 7517). Field names follow the standard, not camelCase.
         */
        Jwk: {
            /**
             * Kty
             * @default RSA
             * @constant
             */
            kty: "RSA";
            /**
             * Kid
             * @description Key ID; matches the `kid` in each token's header.
             * @example 2026-10-k1
             */
            kid: string;
            /**
             * Use
             * @default sig
             * @constant
             */
            use: "sig";
            /**
             * Alg
             * @default RS256
             * @constant
             */
            alg: "RS256";
            /**
             * N
             * @description RSA modulus, base64url.
             */
            n: string;
            /**
             * E
             * @description RSA exponent, base64url.
             * @example AQAB
             */
            e: string;
        };
        /** JwkSet */
        JwkSet: {
            /** Keys */
            keys: components["schemas"]["Jwk"][];
        };
        /** LoginRequest */
        LoginRequest: {
            /**
             * Email
             * @description UofM student email (must end in @myumanitoba.ca).
             * @example ada.lovelace@myumanitoba.ca
             */
            email: string;
            /** Password */
            password: string;
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
             * @description Stable error name for the frontend to check.
             */
            code: string;
            /** Requestid */
            requestId?: string | null;
            /**
             * Errors
             * @description Only on 422: the invalid fields.
             */
            errors?: components["schemas"]["InvalidFieldOut"][] | null;
        };
        /** ResendVerificationRequest */
        ResendVerificationRequest: {
            /**
             * Email
             * @description UofM student email (must end in @myumanitoba.ca).
             * @example ada.lovelace@myumanitoba.ca
             */
            email: string;
        };
        /** SignupRequest */
        SignupRequest: {
            /**
             * Email
             * @description UofM student email (must end in @myumanitoba.ca).
             * @example ada.lovelace@myumanitoba.ca
             */
            email: string;
            /**
             * Password
             * @description At least 10 characters.
             * @example correct horse battery
             */
            password: string;
            /**
             * Firstname
             * @example Ada
             */
            firstName: string;
            /**
             * Lastname
             * @example Lovelace
             */
            lastName: string;
        };
        /** SignupResponse */
        SignupResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Email */
            email: string;
            /**
             * Emailverified
             * @description Always false: a verification email has been sent.
             * @default false
             */
            emailVerified: boolean;
        };
        /**
         * TokenResponse
         * @description An access token. Send it as `Authorization: Bearer <accessToken>`.
         *
         *     The refresh token is never in the body: it's set as an HttpOnly cookie.
         */
        TokenResponse: {
            /**
             * Accesstoken
             * @example eyJhbGciOiJSUzI1NiIsImtpZCI6ImsxIn0...
             */
            accessToken: string;
            /**
             * Tokentype
             * @default Bearer
             * @constant
             */
            tokenType: "Bearer";
            /**
             * Expiresin
             * @description Seconds until the access token expires (900).
             * @example 900
             */
            expiresIn: number;
        };
        /** User */
        User: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Email
             * @example ada.lovelace@myumanitoba.ca
             */
            email: string;
            /**
             * Firstname
             * @example Ada
             */
            firstName: string;
            /**
             * Lastname
             * @example Lovelace
             */
            lastName: string;
            /** Emailverified */
            emailVerified: boolean;
            /**
             * Roles
             * @description Every account is a `user` (rider and driver). `admin` can approve drivers (Sprint 2).
             * @example [
             *       "user"
             *     ]
             */
            roles: ("user" | "admin")[];
        };
        /** VerifyEmailRequest */
        VerifyEmailRequest: {
            /**
             * Token
             * @description The token from the verification link.
             */
            token: string;
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
    signup_auth_signup_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SignupRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SignupResponse"];
                };
            };
            /** @description An account with this email already exists (code `email_taken`) */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Conflict",
                     *       "status": 409,
                     *       "detail": "An account with this email already exists",
                     *       "instance": "/auth/signup",
                     *       "code": "email_taken",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Invalid input, an email that isn't @myumanitoba.ca, or a password under 10 characters (code `invalid_input / email_not_uofm`) */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Unprocessable Content",
                     *       "status": 422,
                     *       "detail": "Invalid input",
                     *       "instance": "/auth/signup",
                     *       "code": "invalid_input",
                     *       "requestId": "b1e2c3d4e5f6",
                     *       "errors": [
                     *         {
                     *           "field": "password",
                     *           "message": "String should have at least 10 characters"
                     *         }
                     *       ]
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    verify_email_auth_verify_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["VerifyEmailRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Unknown or already-used token (code `invalid_token`) */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Bad Request",
                     *       "status": 400,
                     *       "detail": "Unknown or already-used token",
                     *       "instance": "/auth/verify",
                     *       "code": "invalid_token",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description The link has expired; request a new one with /auth/resend-verification (code `token_expired`) */
            410: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Gone",
                     *       "status": 410,
                     *       "detail": "The link has expired; request a new one with /auth/resend-verification",
                     *       "instance": "/auth/verify",
                     *       "code": "token_expired",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Invalid input; `errors` lists the fields (code `invalid_input`) */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Unprocessable Content",
                     *       "status": 422,
                     *       "detail": "Invalid input",
                     *       "instance": "/auth/verify",
                     *       "code": "invalid_input",
                     *       "requestId": "b1e2c3d4e5f6",
                     *       "errors": [
                     *         {
                     *           "field": "password",
                     *           "message": "String should have at least 10 characters"
                     *         }
                     *       ]
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    resend_verification_auth_resend_verification_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ResendVerificationRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Invalid input; `errors` lists the fields (code `invalid_input`) */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Unprocessable Content",
                     *       "status": 422,
                     *       "detail": "Invalid input",
                     *       "instance": "/auth/resend-verification",
                     *       "code": "invalid_input",
                     *       "requestId": "b1e2c3d4e5f6",
                     *       "errors": [
                     *         {
                     *           "field": "password",
                     *           "message": "String should have at least 10 characters"
                     *         }
                     *       ]
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    login_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TokenResponse"];
                };
            };
            /** @description Wrong email or password (one message for both) (code `invalid_credentials`) */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Unauthorized",
                     *       "status": 401,
                     *       "detail": "Wrong email or password (one message for both)",
                     *       "instance": "/auth/login",
                     *       "code": "invalid_credentials",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description The email hasn't been verified yet; the user can resend the email (code `email_not_verified`) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Forbidden",
                     *       "status": 403,
                     *       "detail": "The email hasn't been verified yet; the user can resend the email",
                     *       "instance": "/auth/login",
                     *       "code": "email_not_verified",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Invalid input; `errors` lists the fields (code `invalid_input`) */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Unprocessable Content",
                     *       "status": 422,
                     *       "detail": "Invalid input",
                     *       "instance": "/auth/login",
                     *       "code": "invalid_input",
                     *       "requestId": "b1e2c3d4e5f6",
                     *       "errors": [
                     *         {
                     *           "field": "password",
                     *           "message": "String should have at least 10 characters"
                     *         }
                     *       ]
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    refresh_auth_refresh_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: {
                /** @description Set by login and refresh; HttpOnly. */
                refresh_token?: string | null;
            };
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TokenResponse"];
                };
            };
            /** @description Missing, expired or already-used refresh token (code `invalid_refresh_token`) */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Unauthorized",
                     *       "status": 401,
                     *       "detail": "Missing, expired or already-used refresh token",
                     *       "instance": "/auth/refresh",
                     *       "code": "invalid_refresh_token",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Invalid input; `errors` lists the fields (code `invalid_input`) */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Unprocessable Content",
                     *       "status": 422,
                     *       "detail": "Invalid input",
                     *       "instance": "/auth/refresh",
                     *       "code": "invalid_input",
                     *       "requestId": "b1e2c3d4e5f6",
                     *       "errors": [
                     *         {
                     *           "field": "password",
                     *           "message": "String should have at least 10 characters"
                     *         }
                     *       ]
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    logout_auth_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: {
                /** @description Set by login and refresh; HttpOnly. */
                refresh_token?: string | null;
            };
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Invalid input; `errors` lists the fields (code `invalid_input`) */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Unprocessable Content",
                     *       "status": 422,
                     *       "detail": "Invalid input",
                     *       "instance": "/auth/logout",
                     *       "code": "invalid_input",
                     *       "requestId": "b1e2c3d4e5f6",
                     *       "errors": [
                     *         {
                     *           "field": "password",
                     *           "message": "String should have at least 10 characters"
                     *         }
                     *       ]
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    me_me_get: {
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
                    "application/json": components["schemas"]["User"];
                };
            };
            /** @description Missing or invalid access token (code `unauthorized`) */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Unauthorized",
                     *       "status": 401,
                     *       "detail": "Missing or invalid access token",
                     *       "instance": "/me",
                     *       "code": "unauthorized",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    jwks__well_known_jwks_json_get: {
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
                    "application/json": components["schemas"]["JwkSet"];
                };
            };
        };
    };
}
