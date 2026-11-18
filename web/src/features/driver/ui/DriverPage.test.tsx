import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, problem, renderWithProviders } from "@/shared/testing/render";

import type { DriverProfile } from "../model/driver";
import { DriverPage } from "./DriverPage";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/account/driver",
}));

const maya = { id: "1", email: "maya@myumanitoba.ca", firstName: "Maya", lastName: "Singh", emailVerified: true, roles: ["user"] };
const vehicle = { make: "Honda", model: "Civic", colour: "Grey", plate: "ABC123" };

const profile = (changes: Partial<DriverProfile> = {}): DriverProfile => ({
  status: "none",
  rejectionReason: null,
  documents: { licence: false, insurance: false },
  vehicle: null,
  submittedAt: null,
  reviewedAt: null,
  ...changes,
});

type Answer = { status: number; body?: unknown };

function api(current: DriverProfile, answers: { documents?: Answer; vehicle?: Answer; file?: Answer } = {}) {
  return mockApi({
    "/accounts/me": { status: 200, body: maya },
    "/me/driver/documents/licence": answers.file ?? { status: 200, body: "pdf" },
    "/me/driver/documents": answers.documents ?? { status: 200, body: profile({ status: "pending", documents: { licence: true, insurance: true } }) },
    "/me/driver/vehicle": answers.vehicle ?? { status: 200, body: { ...current, vehicle } },
    "/me/driver": { status: 200, body: current },
  });
}

const pdf = (name: string) => new File(["%PDF"], name, { type: "application/pdf" });
const calls = (fetchSpy: ReturnType<typeof api>, path: string) =>
  fetchSpy.mock.calls.filter(([input]) => new URL(input instanceof Request ? input.url : String(input)).pathname.endsWith(path));

afterEach(() => vi.restoreAllMocks());

describe("DriverPage: documents", () => {
  it("uploads the licence and insurance together, then shows the application as pending", async () => {
    const fetchSpy = api(profile());
    renderWithProviders(<DriverPage />);

    expect(await screen.findByText("Become a driver")).toBeInTheDocument();
    const upload = screen.getByRole("button", { name: "Upload documents" });
    expect(upload).toBeDisabled();

    await userEvent.upload(screen.getByLabelText("Driver's licence"), pdf("licence.pdf"));
    await userEvent.upload(screen.getByLabelText("Proof of insurance"), pdf("insurance.pdf"));
    await userEvent.click(upload);

    expect(await screen.findByText("We're checking your documents")).toBeInTheDocument();
    // What's in the multipart body is checked against the mock API (shared/mocks/driver.test.ts).
    const [put] = calls(fetchSpy, "/me/driver/documents");
    expect((put![0] as Request).method).toBe("PUT");
    expect(screen.getByRole("button", { name: "View Driver's licence" })).toBeInTheDocument();
  });

  it("checks the file type and size before sending anything", async () => {
    const fetchSpy = api(profile());
    const user = userEvent.setup({ applyAccept: false });
    renderWithProviders(<DriverPage />);

    await user.upload(await screen.findByLabelText("Driver's licence"), new File(["gif"], "licence.gif", { type: "image/gif" }));
    expect(screen.getByText("Use a PDF, JPEG or PNG file.")).toBeInTheDocument();

    await user.upload(screen.getByLabelText("Proof of insurance"), new File([new Uint8Array(6 * 1024 * 1024)], "big.pdf", { type: "application/pdf" }));
    expect(screen.getByText(/over 5 MB/)).toBeInTheDocument();

    expect(screen.getByRole("button", { name: "Upload documents" })).toBeDisabled();
    expect(calls(fetchSpy, "/me/driver/documents")).toHaveLength(0);
  });

  it("explains an upload the server refused", async () => {
    api(profile(), { documents: { status: 422, body: problem(422, "file_too_large", "Too large") } });
    renderWithProviders(<DriverPage />);

    await userEvent.upload(await screen.findByLabelText("Driver's licence"), pdf("licence.pdf"));
    await userEvent.upload(screen.getByLabelText("Proof of insurance"), pdf("insurance.pdf"));
    await userEvent.click(screen.getByRole("button", { name: "Upload documents" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("One of the files is over 5 MB.");
  });

  it("shows why an application was rejected, with the form to upload again", async () => {
    api(profile({ status: "rejected", rejectionReason: "The insurance document has expired.", documents: { licence: true, insurance: true }, vehicle }));
    renderWithProviders(<DriverPage />);

    expect(await screen.findByText("Your application wasn't approved")).toBeInTheDocument();
    expect(screen.getByText("The insurance document has expired.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload documents" })).toBeInTheDocument();
  });

  it("lets a pending applicant replace their documents, or keep them", async () => {
    api(profile({ status: "pending", documents: { licence: true, insurance: true }, vehicle }));
    renderWithProviders(<DriverPage />);

    await userEvent.click(await screen.findByRole("button", { name: "Replace documents" }));
    expect(screen.getByRole("button", { name: "Upload documents" })).toBeInTheDocument();
    expect(screen.getByText(/Upload both files again, even if only one has changed/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Keep my current documents" }));
    expect(screen.queryByRole("button", { name: "Upload documents" })).not.toBeInTheDocument();
  });

  it("reminds a pending applicant to add their vehicle", async () => {
    api(profile({ status: "pending", documents: { licence: true, insurance: true } }));
    renderWithProviders(<DriverPage />);

    expect(await screen.findByText(/you can't be approved without it/)).toBeInTheDocument();
  });

  it("shows an approved driver the way to post a trip, with no upload", async () => {
    api(profile({ status: "approved", documents: { licence: true, insurance: true }, vehicle }));
    renderWithProviders(<DriverPage />);

    expect(await screen.findByText("You're approved to drive")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Post a trip" })).toHaveAttribute("href", "/drive/new");
    expect(screen.queryByRole("button", { name: /Upload documents|Replace documents/ })).not.toBeInTheDocument();
  });

  it("opens an uploaded document with the login token, in a new tab", async () => {
    const tab = { location: { href: "" }, close: vi.fn() };
    vi.spyOn(window, "open").mockReturnValue(tab as unknown as Window);
    URL.createObjectURL = vi.fn(() => "blob:licence");
    const fetchSpy = api(profile({ status: "pending", documents: { licence: true, insurance: true }, vehicle }));
    renderWithProviders(<DriverPage />);

    await userEvent.click(await screen.findByRole("button", { name: "View Driver's licence" }));

    await waitFor(() => expect(tab.location.href).toBe("blob:licence"));
    expect(calls(fetchSpy, "/me/driver/documents/licence")).toHaveLength(1);
  });
});

describe("DriverPage: vehicle", () => {
  it("saves a vehicle, with the plate in uppercase, then shows it with Edit", async () => {
    const fetchSpy = api(profile());
    renderWithProviders(<DriverPage />);

    const section = within(await screen.findByRole("region", { name: "Vehicle" }));
    await userEvent.type(section.getByLabelText("Make"), "Honda");
    await userEvent.type(section.getByLabelText("Model"), "Civic");
    await userEvent.type(section.getByLabelText("Colour"), "Grey");
    await userEvent.type(section.getByLabelText("Licence plate"), "abc 123");
    await userEvent.click(section.getByRole("button", { name: "Save vehicle" }));

    expect(await section.findByText("Grey Honda Civic")).toBeInTheDocument();
    expect(section.getByText("Plate ABC123")).toBeInTheDocument();
    const [put] = calls(fetchSpy, "/me/driver/vehicle");
    expect(await (put![0] as Request).json()).toEqual(vehicle);
  });

  it("shows what to fix before sending", async () => {
    const fetchSpy = api(profile());
    renderWithProviders(<DriverPage />);

    const section = within(await screen.findByRole("region", { name: "Vehicle" }));
    await userEvent.type(section.getByLabelText("Licence plate"), "A");
    await userEvent.click(section.getByRole("button", { name: "Save vehicle" }));

    expect(section.getByText("Enter the make.")).toBeInTheDocument();
    expect(section.getByText("Use 2 to 8 letters and numbers, e.g. ABC123.")).toBeInTheDocument();
    expect(calls(fetchSpy, "/me/driver/vehicle")).toHaveLength(0);
  });

  it("shows the server's errors next to the fields", async () => {
    api(profile(), {
      vehicle: { status: 422, body: problem(422, "invalid_input", "Invalid input", { errors: [{ field: "plate", message: "This plate is already registered" }] }) },
    });
    renderWithProviders(<DriverPage />);

    const section = within(await screen.findByRole("region", { name: "Vehicle" }));
    await userEvent.type(section.getByLabelText("Make"), "Honda");
    await userEvent.type(section.getByLabelText("Model"), "Civic");
    await userEvent.type(section.getByLabelText("Colour"), "Grey");
    await userEvent.type(section.getByLabelText("Licence plate"), "ABC123");
    await userEvent.click(section.getByRole("button", { name: "Save vehicle" }));

    expect(await section.findByText("This plate is already registered")).toBeInTheDocument();
  });

  it("edits a saved vehicle, starting from what's saved", async () => {
    api(profile({ status: "pending", documents: { licence: true, insurance: true }, vehicle }));
    renderWithProviders(<DriverPage />);

    const section = within(await screen.findByRole("region", { name: "Vehicle" }));
    await userEvent.click(await section.findByRole("button", { name: "Edit" }));

    expect(section.getByLabelText("Make")).toHaveValue("Honda");
    expect(section.getByLabelText("Licence plate")).toHaveValue("ABC123");
    await userEvent.click(section.getByRole("button", { name: "Cancel" }));
    expect(section.getByText("Grey Honda Civic")).toBeInTheDocument();
  });
});

describe("DriverPage: loading", () => {
  it("offers to try again when the status can't be loaded", async () => {
    mockApi({
      "/accounts/me": { status: 200, body: maya },
      "/me/driver": { status: 500, body: problem(500, "unexpected_error", "Something went wrong") },
    });
    renderWithProviders(<DriverPage />);

    expect(await screen.findByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});
