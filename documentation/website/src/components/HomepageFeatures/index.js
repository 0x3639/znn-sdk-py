import React from "react";
import clsx from "clsx";
import styles from "./styles.module.css";

const FeatureList = [
  {
    title: "Complete stable surface",
    Svg: require("@site/static/img/1_quickstart.svg").default,
    description: (
      <>Use all 76 canonical RPC calls, 72 typed models, and 68 embedded builders.</>
    ),
  },
  {
    title: "Transactions and wallets",
    Svg: require("@site/static/img/2_wallet.svg").default,
    description: (
      <>
        Prepare, inspect, PoW, sign, and publish blocks with interoperable key files.
      </>
    ),
  },
  {
    title: "Offline verified",
    Svg: require("@site/static/img/3_examples.svg").default,
    description: (
      <>
        Run 764 portable vectors and the transport suite without connecting to a node.
      </>
    ),
  },
];

function Feature({ Svg, title, description }) {
  return (
    <div className={clsx("col col--4")}>
      <div className="text--center">
        <Svg className={styles.featureSvg} role="img" />
      </div>
      <div className="text--center padding-horiz--md">
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
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
