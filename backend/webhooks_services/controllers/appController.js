export const getAppUsage = (req, res) => {
  res.json([
    { app_name: "MusicRec", api_calls: 123 },
    { app_name: "BookFinder", api_calls: 45 },
  ]);
};
