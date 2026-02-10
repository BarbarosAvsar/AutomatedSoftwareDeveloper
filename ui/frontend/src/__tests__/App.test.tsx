import { render, screen } from "@testing-library/react";
import { act } from "react";
import { MemoryRouter } from "react-router-dom";
import App from "../App";

const renderRoute = (route: string) =>
  render(
    <MemoryRouter initialEntries={[route]}>
      <App />
    </MemoryRouter>
  );

describe("AEC routes", () => {
  it("renders the dashboard route", () => {
    renderRoute("/");
    expect(screen.getByText(/Portfolio Dashboard/i)).toBeInTheDocument();
  });

  it("renders the requirements studio route", () => {
    renderRoute("/requirements");
    expect(screen.getByRole("heading", { name: /Requirements Studio/i })).toBeInTheDocument();
    expect(screen.getByText(/90-second guide/i)).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /Workflow map \(human \+ agent responsibilities\)/i })
    ).toBeInTheDocument();
    expect(screen.getByText(/Human-centered UI guidelines/i)).toBeInTheDocument();
    expect(screen.getByText(/Settings explained \(plain language\)/i)).toBeInTheDocument();
  });

  it("updates progress bar on mocked events", () => {
    renderRoute("/project/alpha");
    act(() => {
      const event = new CustomEvent("aec-progress", { detail: { percent: 80 } });
      window.dispatchEvent(event);
    });
    expect(screen.getByText(/Progress: 80%/i)).toBeInTheDocument();
  });
});
