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
    "/me/driver": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * My driver status
         * @description Whether the logged-in user has applied to drive, and where it stands: `none`, `pending`, `approved` or `rejected` (with the reason).
         */
        get: operations["my_driver_profile_me_driver_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/me/driver/documents": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Upload my licence and insurance
         * @description Both files, PDF, JPEG or PNG, up to 5 MB each. Uploading (again, after a rejection) sets the status to `pending`. Only the driver and admins can open them.
         */
        put: operations["upload_documents_me_driver_documents_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/me/driver/documents/{kind}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Open one of my documents */
        get: operations["my_document_me_driver_documents__kind__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/me/driver/vehicle": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Save my vehicle
         * @description Make, model, colour and plate. The plate is stored in uppercase.
         */
        put: operations["save_vehicle_me_driver_vehicle_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/admin/drivers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Driver applications
         * @description Applications with the given status, oldest first (default: pending).
         */
        get: operations["list_drivers_admin_drivers_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/admin/drivers/{user_id}/documents/{kind}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Open a driver's document */
        get: operations["driver_document_admin_drivers__user_id__documents__kind__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/admin/drivers/{user_id}/approve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Approve a driver
         * @description They can post trips straight away, without logging in again. Publishes `DriverApproved`.
         */
        post: operations["approve_driver_admin_drivers__user_id__approve_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/admin/drivers/{user_id}/reject": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Reject a driver
         * @description The reason is shown to the driver, who can upload new documents. Publishes `DriverRejected`.
         */
        post: operations["reject_driver_admin_drivers__user_id__reject_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/users/{user_id}/profile": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * A user's public profile
         * @description First name, rating, completed trips, and (for approved drivers) their vehicle without its plate. Never their email or last name.
         */
        get: operations["public_profile_users__user_id__profile_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/internal/users": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Names, ratings and no-shows
         * @description For Trips (the driver's list of requests, auto-accept). No email.
         */
        get: operations["internal_users_internal_users_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/internal/contacts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Names and emails
         * @description For Notifications only: where to send emails.
         */
        get: operations["internal_contacts_internal_contacts_get"];
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
        /**
         * AdminDriver
         * @description A driver application, as an admin sees it.
         */
        AdminDriver: {
            /**
             * Userid
             * Format: uuid
             */
            userId: string;
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
            /**
             * Email
             * @example ada.lovelace@myumanitoba.ca
             */
            email: string;
            status: components["schemas"]["DriverStatus"];
            vehicle: components["schemas"]["Vehicle"] | null;
            documents: components["schemas"]["DocumentsUploaded"];
            /** Submittedat */
            submittedAt: string | null;
            /** Reviewedat */
            reviewedAt: string | null;
            /** Rejectionreason */
            rejectionReason: string | null;
        };
        /** Body_upload_documents_me_driver_documents_put */
        Body_upload_documents_me_driver_documents_put: {
            /**
             * Licence
             * @description Driver's licence.
             */
            licence: string;
            /**
             * Insurance
             * @description Proof of insurance.
             */
            insurance: string;
        };
        /**
         * DocumentKind
         * @enum {string}
         */
        DocumentKind: "licence" | "insurance";
        /** DocumentsUploaded */
        DocumentsUploaded: {
            /** Licence */
            licence: boolean;
            /** Insurance */
            insurance: boolean;
        };
        /**
         * DriverProfile
         * @description The logged-in user's own driver status.
         */
        DriverProfile: {
            status: components["schemas"]["DriverStatus"];
            /**
             * Rejectionreason
             * @description Set when `status` is `rejected`.
             */
            rejectionReason: string | null;
            documents: components["schemas"]["DocumentsUploaded"];
            vehicle: components["schemas"]["Vehicle"] | null;
            /**
             * Submittedat
             * @description When documents were last uploaded.
             */
            submittedAt: string | null;
            /**
             * Reviewedat
             * @description When an admin last decided.
             */
            reviewedAt: string | null;
        };
        /**
         * DriverStatus
         * @enum {string}
         */
        DriverStatus: "none" | "pending" | "approved" | "rejected";
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
        /**
         * InternalContact
         * @description For Notifications only: where to send emails.
         */
        InternalContact: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Firstname */
            firstName: string;
            /** Email */
            email: string;
        };
        /** InternalContacts */
        InternalContacts: {
            /**
             * Contacts
             * @description Unknown IDs are left out.
             */
            contacts: components["schemas"]["InternalContact"][];
        };
        /**
         * InternalUser
         * @description For Trips: names, ratings and no-shows. No email.
         */
        InternalUser: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Firstname */
            firstName: string;
            /** Rating */
            rating: number | null;
            /** Ratingcount */
            ratingCount: number;
            /** Tripcount */
            tripCount: number;
            /** Noshowcount */
            noShowCount: number;
        };
        /** InternalUsers */
        InternalUsers: {
            /**
             * Users
             * @description Unknown IDs are left out.
             */
            users: components["schemas"]["InternalUser"][];
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
        /**
         * PublicProfile
         * @description What any logged-in student can see about another.
         */
        PublicProfile: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Firstname
             * @example Ada
             */
            firstName: string;
            /**
             * Rating
             * @description Average rating; null if they have no ratings yet.
             */
            rating: number | null;
            /** Ratingcount */
            ratingCount: number;
            /**
             * Tripcount
             * @description Completed trips, as a driver or rider.
             */
            tripCount: number;
            /**
             * Isdriver
             * @description An approved driver.
             */
            isDriver: boolean;
            /** @description Approved drivers only. */
            vehicle: components["schemas"]["PublicVehicle"] | null;
        };
        /**
         * PublicVehicle
         * @description A vehicle without its plate.
         */
        PublicVehicle: {
            /**
             * Make
             * @example Honda
             */
            make: string;
            /**
             * Model
             * @example Civic
             */
            model: string;
            /**
             * Colour
             * @example Blue
             */
            colour: string;
        };
        /** RejectDriverRequest */
        RejectDriverRequest: {
            /**
             * Reason
             * @description Shown to the driver, so they know what to fix.
             * @example The insurance document has expired.
             */
            reason: string;
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
        /** Vehicle */
        Vehicle: {
            /**
             * Make
             * @example Honda
             */
            make: string;
            /**
             * Model
             * @example Civic
             */
            model: string;
            /**
             * Colour
             * @example Blue
             */
            colour: string;
            /**
             * Plate
             * @description 2 to 8 letters and digits, no spaces. Stored and returned in uppercase. Only shown to the driver, admins, and riders accepted on their trips.
             * @example ABC123
             */
            plate: string;
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
    my_driver_profile_me_driver_get: {
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
                    "application/json": components["schemas"]["DriverProfile"];
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
                     *       "instance": "/me/driver",
                     *       "code": "unauthorized",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    upload_documents_me_driver_documents_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_upload_documents_me_driver_documents_put"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DriverProfile"];
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
                     *       "instance": "/me/driver/documents",
                     *       "code": "unauthorized",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Already approved (code `driver_already_approved`) */
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
                     *       "detail": "Already approved",
                     *       "instance": "/me/driver/documents",
                     *       "code": "driver_already_approved",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Invalid input, a file that isn't PDF, JPEG or PNG, or one over 5 MB (code `invalid_input / unsupported_file_type / file_too_large`) */
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
                     *       "instance": "/me/driver/documents",
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
    my_document_me_driver_documents__kind__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                kind: components["schemas"]["DocumentKind"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description The file as uploaded. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/pdf": unknown;
                    "image/jpeg": unknown;
                    "image/png": unknown;
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
                     *       "instance": "/me/driver/documents/{kind}",
                     *       "code": "unauthorized",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description No document of this kind uploaded (code `document_not_found`) */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Not Found",
                     *       "status": 404,
                     *       "detail": "No document of this kind uploaded",
                     *       "instance": "/me/driver/documents/{kind}",
                     *       "code": "document_not_found",
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
                     *       "instance": "/me/driver/documents/{kind}",
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
    save_vehicle_me_driver_vehicle_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["Vehicle"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DriverProfile"];
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
                     *       "instance": "/me/driver/vehicle",
                     *       "code": "unauthorized",
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
                     *       "instance": "/me/driver/vehicle",
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
    list_drivers_admin_drivers_get: {
        parameters: {
            query?: {
                status?: components["schemas"]["DriverStatus"];
            };
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
                    "application/json": components["schemas"]["AdminDriver"][];
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
                     *       "instance": "/admin/drivers",
                     *       "code": "unauthorized",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Only admins can do this (code `forbidden`) */
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
                     *       "detail": "Only admins can do this",
                     *       "instance": "/admin/drivers",
                     *       "code": "forbidden",
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
                     *       "instance": "/admin/drivers",
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
    driver_document_admin_drivers__user_id__documents__kind__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
                kind: components["schemas"]["DocumentKind"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description The file as uploaded. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/pdf": unknown;
                    "image/jpeg": unknown;
                    "image/png": unknown;
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
                     *       "instance": "/admin/drivers/{user_id}/documents/{kind}",
                     *       "code": "unauthorized",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Only admins can do this (code `forbidden`) */
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
                     *       "detail": "Only admins can do this",
                     *       "instance": "/admin/drivers/{user_id}/documents/{kind}",
                     *       "code": "forbidden",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description No document of this kind uploaded (code `document_not_found`) */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Not Found",
                     *       "status": 404,
                     *       "detail": "No document of this kind uploaded",
                     *       "instance": "/admin/drivers/{user_id}/documents/{kind}",
                     *       "code": "document_not_found",
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
                     *       "instance": "/admin/drivers/{user_id}/documents/{kind}",
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
    approve_driver_admin_drivers__user_id__approve_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
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
                    "application/json": components["schemas"]["AdminDriver"];
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
                     *       "instance": "/admin/drivers/{user_id}/approve",
                     *       "code": "unauthorized",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Only admins can do this (code `forbidden`) */
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
                     *       "detail": "Only admins can do this",
                     *       "instance": "/admin/drivers/{user_id}/approve",
                     *       "code": "forbidden",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description No driver application for this user (code `driver_not_found`) */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Not Found",
                     *       "status": 404,
                     *       "detail": "No driver application for this user",
                     *       "instance": "/admin/drivers/{user_id}/approve",
                     *       "code": "driver_not_found",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description The application isn't pending (code `driver_not_pending`) */
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
                     *       "detail": "The application isn't pending",
                     *       "instance": "/admin/drivers/{user_id}/approve",
                     *       "code": "driver_not_pending",
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
                     *       "instance": "/admin/drivers/{user_id}/approve",
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
    reject_driver_admin_drivers__user_id__reject_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RejectDriverRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AdminDriver"];
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
                     *       "instance": "/admin/drivers/{user_id}/reject",
                     *       "code": "unauthorized",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Only admins can do this (code `forbidden`) */
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
                     *       "detail": "Only admins can do this",
                     *       "instance": "/admin/drivers/{user_id}/reject",
                     *       "code": "forbidden",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description No driver application for this user (code `driver_not_found`) */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Not Found",
                     *       "status": 404,
                     *       "detail": "No driver application for this user",
                     *       "instance": "/admin/drivers/{user_id}/reject",
                     *       "code": "driver_not_found",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description The application isn't pending (code `driver_not_pending`) */
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
                     *       "detail": "The application isn't pending",
                     *       "instance": "/admin/drivers/{user_id}/reject",
                     *       "code": "driver_not_pending",
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
                     *       "instance": "/admin/drivers/{user_id}/reject",
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
    public_profile_users__user_id__profile_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
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
                    "application/json": components["schemas"]["PublicProfile"];
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
                     *       "instance": "/users/{user_id}/profile",
                     *       "code": "unauthorized",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description No user with this ID (code `user_not_found`) */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Not Found",
                     *       "status": 404,
                     *       "detail": "No user with this ID",
                     *       "instance": "/users/{user_id}/profile",
                     *       "code": "user_not_found",
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
                     *       "instance": "/users/{user_id}/profile",
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
    internal_users_internal_users_get: {
        parameters: {
            query: {
                /** @description Repeat for each user: `?ids=...&ids=...`. */
                ids: string[];
            };
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
                    "application/json": components["schemas"]["InternalUsers"];
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
                     *       "instance": "/internal/users",
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
    internal_contacts_internal_contacts_get: {
        parameters: {
            query: {
                /** @description Repeat for each user: `?ids=...&ids=...`. */
                ids: string[];
            };
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
                    "application/json": components["schemas"]["InternalContacts"];
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
                     *       "instance": "/internal/contacts",
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
}
