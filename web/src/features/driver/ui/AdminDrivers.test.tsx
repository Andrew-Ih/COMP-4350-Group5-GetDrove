import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, problem, renderWithProviders } from "@/shared/testing/render";

import type { AdminDriver } from "../model/driver";
import { AdminDrivers } from "./AdminDrivers";

const { replace } = vi.hoisted(() => ({ replace: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace }),
  usePathname: () => "/admin/drivers",
}));

const alex = { id: "a1", email: "admin@myumanitoba.ca", firstName: "Alex", lastName: "Admin", emailVerified: true, roles: ["user", "admin"] };
const maya = { ...alex, id: "m1", firstName: "Maya", roles: ["user"] };

const applicant = (userId: string, firstName: string, changes: Partial<AdminDriver> = {}): AdminDriver => ({
  userId,
  firstName,
  lastName: "Patel",
  email: `${firstName.toLowerCase()}@myumanitoba.ca`,
  status: "pending",
  vehicle: { make: "Honda", model: "Civic", colour: "Grey", plate: "GDR123" },
  documents: { licence: true, insurance: true },
  submittedAt: "2026-11-10T15:00:00Z",
  reviewedAt: null,
  rejectionReason: null,
  ...changes,
});

const PRIYA = applicant("u1", "Priya");
const DANIEL = applicant("u2", "Daniel", { vehicle: null, documents: { licence: true, insurance: false } });

type Answer = { status: number; body?: unknown };

/** The admin, their applications by status (answered in turn), and what deciding answers. */
function api({
  me = alex,
  lists = { pending: [{ status: 200, body: [PRIYA, DANIEL] }] },
  decision,
}: { me?: typeof alex; lists?: Partial<Record<string, Answer[]>>; decision?: Answer } = {}) {
  const asked: Record<string, number> = {};
  return mockApi({
    "/accounts/me": { status: 200, body: me },
    "/approve": decision ?? { status: 200, body: { ...PRIYA, status: "approved" } },
    "/reject": decision ?? { status: 200, body: { ...PRIYA, status: "rejected" } },
    "/documents/licence": { status: 200, body: "pdf" },
    "/admin/drivers": (url) => {
      const status = url.searchParams.get("status") ?? "pending";
      const answers = lists[status] ?? [{ status: 200, body: [] }];
      const i = asked[status] ?? 0;
      asked[status] = i + 1;
      return answers[Math.min(i, answers.length - 1)]!;
    },
  });
}

const sent = (spy: ReturnType<typeof api>, path: string) =>
  spy.mock.calls.map(([input]) => input as Request).filter((r) => r.method === "POST" && r.url.endsWith(path));

afterEach(() => {
  vi.restoreAllMocks();
  replace.mockClear();
});

describe("AdminDrivers", () => {
  it("lists pending applications with the vehicle and documents", async () => {
    api();
    renderWithProviders(<AdminDrivers />);

    const list = await screen.findByRole("list", { name: "Pending applications" });
    const [priya, daniel] = within(list).getAllByRole("listitem");
    expect(priya).toHaveTextContent("Priya Patel");
    expect(priya).toHaveTextContent("priya@myumanitoba.ca");
    expect(priya).toHaveTextContent("Honda Civic, Grey · GDR123");
    expect(within(priya!).getByRole("button", { name: "View driver's licence for Priya Patel" })).toBeInTheDocument();
    expect(within(priya!).getByRole("button", { name: "View proof of insurance for Priya Patel" })).toBeInTheDocument();
    expect(daniel).toHaveTextContent("No vehicle added yet");
    expect(daniel).toHaveTextContent("No proof of insurance");
  });

  it("approves an application, and the list updates", async () => {
    const spy = api({ lists: { pending: [{ status: 200, body: [PRIYA, DANIEL] }, { status: 200, body: [DANIEL] }] } });
    renderWithProviders(<AdminDrivers />);

    const priya = await screen.findByRole("group", { name: "Priya Patel" });
    await userEvent.click(within(priya).getByRole("button", { name: "Approve" }));

    await waitFor(() => expect(screen.queryByRole("group", { name: "Priya Patel" })).not.toBeInTheDocument());
    expect(sent(spy, "/admin/drivers/u1/approve")).toHaveLength(1);
    expect(screen.getByRole("group", { name: "Daniel Patel" })).toBeInTheDocument();
  });

  it("rejects with a reason the driver will see", async () => {
    const spy = api({ lists: { pending: [{ status: 200, body: [PRIYA] }, { status: 200, body: [] }] } });
    renderWithProviders(<AdminDrivers />);

    const priya = await screen.findByRole("group", { name: "Priya Patel" });
    await userEvent.click(within(priya).getByRole("button", { name: "Reject" }));
    await userEvent.click(within(priya).getByRole("button", { name: "Reject application" }));
    expect(within(priya).getByRole("alert")).toHaveTextContent("Say what the driver needs to fix.");
    expect(sent(spy, "/reject")).toHaveLength(0);

    await userEvent.type(within(priya).getByRole("textbox", { name: /Why are you rejecting/ }), "  The insurance has expired. ");
    await userEvent.click(within(priya).getByRole("button", { name: "Reject application" }));

    expect(await screen.findByText("No applications are waiting. You're all caught up.")).toBeInTheDocument();
    const [request] = sent(spy, "/admin/drivers/u1/reject");
    expect(await request!.json()).toEqual({ reason: "The insurance has expired." });
  });

  it("can cancel rejecting", async () => {
    api();
    renderWithProviders(<AdminDrivers />);

    const priya = await screen.findByRole("group", { name: "Priya Patel" });
    await userEvent.click(within(priya).getByRole("button", { name: "Reject" }));
    await userEvent.click(within(priya).getByRole("button", { name: "Cancel" }));
    expect(within(priya).getByRole("button", { name: "Approve" })).toBeInTheDocument();
  });

  it("explains when an applicant without a vehicle can't be approved", async () => {
    api({ decision: { status: 409, body: problem(409, "vehicle_missing", "The driver hasn't saved a vehicle yet") } });
    renderWithProviders(<AdminDrivers />);

    const daniel = await screen.findByRole("group", { name: "Daniel Patel" });
    await userEvent.click(within(daniel).getByRole("button", { name: "Approve" }));

    expect(await within(daniel).findByRole("alert")).toHaveTextContent("They haven't added their vehicle yet");
  });

  it("shows decided applications with their reason", async () => {
    api({
      lists: {
        pending: [{ status: 200, body: [] }],
        rejected: [{ status: 200, body: [applicant("u3", "Sam", { status: "rejected", reviewedAt: "2026-11-11T15:00:00Z", rejectionReason: "Expired insurance." })] }],
      },
    });
    renderWithProviders(<AdminDrivers />);

    await userEvent.click(await screen.findByRole("tab", { name: "Rejected" }));

    const sam = await screen.findByRole("group", { name: "Sam Patel" });
    expect(sam).toHaveTextContent(/Rejected .*: “Expired insurance\.”/);
    expect(within(sam).queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  });

  it("opens a document in a new tab", async () => {
    const tab = { location: { href: "" }, close: vi.fn() };
    vi.spyOn(window, "open").mockReturnValue(tab as unknown as Window);
    URL.createObjectURL = vi.fn(() => "blob:licence");
    api();
    renderWithProviders(<AdminDrivers />);

    await userEvent.click(await screen.findByRole("button", { name: "View driver's licence for Priya Patel" }));

    await waitFor(() => expect(tab.location.href).toBe("blob:licence"));
  });

  it("sends anyone who isn't an admin away, without loading applications", async () => {
    const spy = api({ me: maya });
    renderWithProviders(<AdminDrivers />);

    expect(await screen.findByText("Only admins can see this page.")).toBeInTheDocument();
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/"));
    expect(spy.mock.calls.some(([input]) => (input as Request).url.includes("/admin/drivers"))).toBe(false);
  });

  it("offers to try again when the applications can't be loaded", async () => {
    api({ lists: { pending: [{ status: 500, body: problem(500, "unexpected_error", "Something went wrong") }, { status: 200, body: [PRIYA] }] } });
    renderWithProviders(<AdminDrivers />);

    await userEvent.click(await screen.findByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("group", { name: "Priya Patel" })).toBeInTheDocument();
  });
});
