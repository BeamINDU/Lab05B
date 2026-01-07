import { NextPage } from "next";

const Home: NextPage = () => {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  if (!apiUrl) {
    console.error("API URL is not defined. Check your .env.local file.");
  }

  return (
    <div>
      <h1>API URL: {apiUrl || "API URL is not defined"}</h1>
    </div>
  );
};

export default Home;
