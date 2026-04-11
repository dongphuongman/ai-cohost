import { render } from "preact";
import { initSentry } from "@/lib/sentry";
import "@/styles.css";
import { Popup } from "./popup";

initSentry();
render(<Popup />, document.getElementById("app")!);
