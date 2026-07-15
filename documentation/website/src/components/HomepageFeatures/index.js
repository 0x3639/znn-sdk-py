import React from "react";
import clsx from "clsx";
import styles from "./styles.module.css";

const StatList = [
  { value: "76", label: "RPC calls" },
  { value: "72", label: "Typed models" },
  { value: "68", label: "Builders" },
  { value: "764", label: "Test vectors" },
  { value: "0", label: "Transaction fees" },
];

const FeatureList = [
  {
    title: "Complete stable surface",
    description: (
      <>Use all 76 canonical RPC calls, 72 typed models, and 68 embedded builders.</>
    ),
  },
  {
    title: "Transactions and wallets",
    description: (
      <>
        Prepare, inspect, PoW, sign, and publish blocks with interoperable key files.
      </>
    ),
  },
  {
    title: "Offline verified",
    description: (
      <>
        Run 764 portable vectors and the transport suite without connecting to a node.
      </>
    ),
  },
];

function Stat({ value, label }) {
  return (
    <div className={styles.stat}>
      <span className={styles.statValue}>{value}</span>
      <span className={clsx("text-ledger", styles.statLabel)}>{label}</span>
    </div>
  );
}

function Feature({ title, description }) {
  return (
    <div className={clsx("col col--4", styles.featureCol)}>
      <div className={clsx("card", styles.featureCard)}>
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
    </div>
  );
}

export default function HomepageFeatures() {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className={styles.stats}>
          {StatList.map((props, idx) => (
            <Stat key={idx} {...props} />
          ))}
        </div>
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
