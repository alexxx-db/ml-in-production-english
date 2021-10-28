# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC 
# MAGIC <div style="text-align: center; line-height: 0; padding-top: 9px;">
# MAGIC   <img src="https://databricks.com/wp-content/uploads/2018/03/db-academy-rgb-1200px.png" alt="Databricks Learning" style="width: 600px">
# MAGIC </div>

# COMMAND ----------

# MAGIC %md # Drift Monitoring
# MAGIC 
# MAGIC Monitoring models over time entails safeguarding against drift in model performance as well as breaking changes.  In this lesson, you explore solutions to drift and implement statistical methods for identifying drift. 
# MAGIC 
# MAGIC ## ![Spark Logo Tiny](https://files.training.databricks.com/images/105/logo_spark_tiny.png) In this lesson you:<br>
# MAGIC  - Analyze the types of drift and related statistical methods
# MAGIC  - Test for drift using statistical tests
# MAGIC  - Monitor for drift using summary statistics
# MAGIC  - Apply a comprehensive monitoring solution
# MAGIC  - Explore architectual considerations in monitoring for drift

# COMMAND ----------

# MAGIC %md
# MAGIC ## Drift Monitoring
# MAGIC 
# MAGIC The majority of machine learning solutions assume that data is generated according to a stationary probability distribution. However, because most datasets involving human activity change over time, machine learning solutions often go stale. 
# MAGIC 
# MAGIC For example, a model trained to predict restaurant sales before the COVID-19 pandemic would likely not be an accurate model of restaurant sales during the pandemic. The distribution under which it was trained changed, or drifted, over time. 
# MAGIC 
# MAGIC Drift is composed of number of different types:<br><br> 
# MAGIC 
# MAGIC * **Data Drift**
# MAGIC   * **Data Changes**
# MAGIC     * In practice, upstream data changes is one of the most common sources of drift
# MAGIC     * For instance, null records from a changed ETL task
# MAGIC   * **Feature Drift** 
# MAGIC     * Change in the distribution of an input feature(s)
# MAGIC     * Change in \\(P(X)\\)
# MAGIC   * **Label Drift**
# MAGIC     * Change in the distribution of the label in the data
# MAGIC     * Change in  \\(P(Y)\\)
# MAGIC   * **Prediction Drift** 
# MAGIC       * Change in the distribution of the predicted label given by the model
# MAGIC       * Change in \\(P(\hat{Y}| X)\\) 
# MAGIC * **Concept Drift** 
# MAGIC   * Change in the relationship between input variables and label
# MAGIC   * Change in distribution of \\(P(Y| X)\\)
# MAGIC   * Likely results in an invalid current model
# MAGIC 
# MAGIC **A rigorous monitoring solution for drift entails monitoring each cause of drift.**

# COMMAND ----------

# MAGIC %md 
# MAGIC 
# MAGIC It is important to note that each situation will need to be handled differently and that the presence of drift does not immediately indicate a need to replace the current model. 
# MAGIC 
# MAGIC For example:
# MAGIC * Imagine a model designed to predict snow cone sales with temperature as an input variable. If more recent data has higher temperatures and higher snow cone sales, we have both feature and label drift, but as long as the model is performing well, then there is not an issue. However, we might still want to take other business action given the change, so it is important to monitor for this anyway. 
# MAGIC 
# MAGIC * However, if temperature rose and sales increased, but our predictions did not match this change, we could have concept drift and will need to retrain the model. 
# MAGIC 
# MAGIC * In either case, we may want to alert the company of the changes in case they impact other business processes, so it is important to track all potential drift. 
# MAGIC 
# MAGIC **In order to best adapt to possible changes, we compare data and models across time windows to identify any kind of drift that could be occuring, and then analyze and diagnose the issue after looking closer.** 

# COMMAND ----------

# MAGIC %md
# MAGIC ## Testing for Drift
# MAGIC 
# MAGIC The essence of drift monitoring is **running statistical tests on time windows of data.** This allows us to detect drift and localize it to specific root causes. Here are some solutions:
# MAGIC 
# MAGIC **Numeric Features**
# MAGIC * Summary Statisitcs
# MAGIC   * Mean, Median, Variance, Missing value count, Max, Min
# MAGIC * Tests
# MAGIC   * [Jensen-Shannon](https://en.wikipedia.org/wiki/Jensen%E2%80%93Shannon_divergence)
# MAGIC     - This method provides a smoothed and normalized metric
# MAGIC   * [Two-Sample Kolmogorov-Smirnov (KS)](https://en.wikipedia.org/wiki/Kolmogorov%E2%80%93Smirnov_test), [Mann-Whitney](https://en.wikipedia.org/wiki/Mann%E2%80%93Whitney_U_test), or [Wilcoxon tests](https://en.wikipedia.org/wiki/Wilcoxon_signed-rank_test).
# MAGIC     - Note: These tests vary largely in their assumption of normalcy and ability to handle larger data sizes
# MAGIC     - Do a check of normalcy and choose the appropriate test based on this (e.g. Mann-Whitney is more permissive of skew) 
# MAGIC   * [Wasserstein Distance](https://en.wikipedia.org/wiki/Wasserstein_metric)
# MAGIC   * [Kullback–Leibler divergence](https://en.wikipedia.org/wiki/Kullback%E2%80%93Leibler_divergence)
# MAGIC 
# MAGIC     
# MAGIC **Categorical Features**
# MAGIC * Summary Statistics
# MAGIC   * Mode, Number of unique values, Number of missing values
# MAGIC * Tests
# MAGIC   * [One-way Chi-Squared Test](https://en.wikipedia.org/wiki/Chi-squared_test)
# MAGIC   * [Chi-Squared Contingency Test](https://en.wikipedia.org/wiki/Chi-squared_test)
# MAGIC   * [Fisher's Exact Test](https://en.wikipedia.org/wiki/Fisher%27s_exact_test)
# MAGIC 
# MAGIC We also might want to store the relationship between the input variables and label. In that case, we handle this differently depending on the label variable type. 
# MAGIC 
# MAGIC **Numeric Comparisons**
# MAGIC * [Pearson Coefficient](https://en.wikipedia.org/wiki/Pearson_correlation_coefficient)
# MAGIC 
# MAGIC **Categorical Comparisons** 
# MAGIC * [Contingency Tables](https://en.wikipedia.org/wiki/Contingency_table#:~:text=In%20statistics%2C%20a%20contingency%20table,frequency%20distribution%20of%20the%20variables.&text=They%20provide%20a%20basic%20picture,help%20find%20interactions%20between%20them.)
# MAGIC 
# MAGIC Let's try them out!

# COMMAND ----------

# MAGIC %run ../Includes/Classroom-Setup

# COMMAND ----------

# MAGIC %md
# MAGIC Use the **Two-Sample Kolmogorov-Smirnov (KS) Test** for numeric features. This test determines whether or not two different samples come from the same distribution. This test:<br><br>
# MAGIC 
# MAGIC - Returns a higher KS statistic when there is a higher probability of having two different distributions
# MAGIC - Returns a lower P value the higher the statistical significance
# MAGIC 
# MAGIC In practice, we need a thershold for the p-value, where we will consider it ***unlikely enough*** that the samples did not come from the same distribution. Usually this threshold, or alpha level, is 0.05. 

# COMMAND ----------

import seaborn as sns
from scipy.stats import gaussian_kde, truncnorm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from scipy.spatial import distance

def plot_distribution(distibution_1, distibution_2):
    """
    Plots the two given distributions 

    :param distribution_1: rv_continuous 
    :param distribution_2: rv_continuous 

    """
    sns.kdeplot(distibution_1, shade=True, color="g", label=1)
    sns.kdeplot(distibution_2, shade=True, color="b", label=2)
    plt.legend(loc="upper right", borderaxespad=0)

def get_truncated_normal(mean=0, sd=1, low=0.2, upp=0.8, n_size=1000, seed=999):
    """
    Generates truncated normal distribution based on given mean, standard deviation, lower bound, upper bound and sample size 

    :param mean: float, mean used to create the distribution 
    :param sd: float, standard deviation used to create distribution
    :param low: float, lower bound used to create the distribution 
    :param upp: float, upper bound used to create the distribution 
    :param n_size: integer, desired sample size 

    :return distb: rv_continuous 
    """
    a = (low-mean) / sd
    b = (upp-mean) / sd
    distb = truncnorm(a, b, loc=mean, scale=sd).rvs(n_size)
    return distb

def calculate_ks(distibution_1, distibution_2):
    """
    Helper function that calculated the KS stat and plots the two distributions used in the calculation 

    :param distribution_1: rv_continuous
    :param distribution_2: rv_continuous 

    :return p_value: float, resulting p-value from KS calculation
    :return ks_drift: bool, detection of significant difference across the distributions 
    """
    base, comp = distibution_1, distibution_2
    p_value = np.round(stats.ks_2samp(base, comp)[0],3)
    ks_drift = str(p_value < 0.05)

    # Generate plots
    plot_distribution(base, comp)
    label = f"KS Stat suggests model drift: {ks_drift} \n P-value = {p_value}"
    plt.title(label, loc="center")
    return p_value, ks_drift

def calculate_js_distance(distibution_1, distibution_2):
    """
    Helper function that calculated the JS distance and plots the two distributions used in the calculation 

    :param distribution_1: rv_continuous
    :param distribution_2: rv_continuous 

    :return js_stat: float, resulting distance measure from JS calculation
    :return js_drift: bool, detection of significant difference across the distributions 
    """
    base, comp = np.sort(distibution_1), np.sort(distibution_2)
    js_stat = distance.jensenshannon(base, comp, base=2)
    js_stat_string = str(np.round(js_stat, 3))
    js_drift = str(js_stat > 0.2)

    # Generate plot
    plot_distribution(base, comp)
    nl = "\n"
    label = f"Jensen Shannon suggests model drift: {js_drift} {nl} JS Distance = {js_stat_string}"
    plt.title(label, loc="center")

    return js_stat, js_drift

# COMMAND ----------

# MAGIC %md 
# MAGIC Let's start with a sample size of 1000.

# COMMAND ----------

calculate_ks(get_truncated_normal(upp=.80, n_size=1000), 
             get_truncated_normal(upp=.79, n_size=1000) 
            )

# COMMAND ----------

# MAGIC %md Great! We can see the distributions look pretty similar and we have a high p-value. Now, let's increase the sample size and see its impact on the p-value...Let's set `N = 10,000`

# COMMAND ----------

calculate_ks(get_truncated_normal(upp=.80, n_size=10000), 
             get_truncated_normal(upp=.79, n_size=10000)
            )

# COMMAND ----------

# MAGIC %md 
# MAGIC Wow! Increasing the sample size decreased the p-value significantly. Let's bump up the sample size by one more factor of 10: `N = 100,000`

# COMMAND ----------

calculate_ks(get_truncated_normal(upp=.80, n_size=100000), 
             get_truncated_normal(upp=.79, n_size=100000) 
            )

# COMMAND ----------

# MAGIC %md 
# MAGIC With the increase sample size, our `ks_stat` has dropped to near zero indicating that our two samples are significantly different. However, by just visually looking at the plot of our two overlapping distributions, they look pretty similar. Caculating the `ks_stat` can be useful when determining the similarity between two distributions, however you can quickly run into limitations based on sample size. So how can we test for distribution similarity when we have a *large sample size*?

# COMMAND ----------

# MAGIC %md
# MAGIC 
# MAGIC #### Jensen Shannon
# MAGIC Jensen Shannon distance is more appropriate for drift detection since it meaures the distance between two probability distributions **and** it is smoothed and normalized. When log base 2 is used for the distance calculation, the value is bounded between 0 and 1, where 0 means the distributions are identical and 1 means the distributions have no similarity. The Jensen Shannon distance is defined as the square root of the [Jensen Shannon divergence](https://en.wikipedia.org/wiki/Jensen%E2%80%93Shannon_divergence):
# MAGIC 
# MAGIC 
# MAGIC 
# MAGIC ![Jensen Shannon Divergence](https://miro.medium.com/max/1400/1*viATYZeg9SiT-ZdzYGjKYA.png)
# MAGIC 
# MAGIC 
# MAGIC where *m* is defined as the pointwise mean of *p* and *q* and *H(p)* is defined as the entropy function:
# MAGIC 
# MAGIC ![JS Entropy](https://miro.medium.com/max/1400/1*NSIn8OVTKufpSlvOOoXWQg.png)

# COMMAND ----------

## Verify with two identical distributions 
distance.jensenshannon(p=[1.0, 0.0, 1.0], q=[1.0, 0.0, 1.0], base=2.0)

# COMMAND ----------

# MAGIC %md
# MAGIC Let's try this example again with `N = 1,000`.

# COMMAND ----------

calculate_js_distance(get_truncated_normal(upp=.80, n_size=1000), 
                      get_truncated_normal(upp=.79, n_size=1000)
                     )

# COMMAND ----------

# MAGIC %md 
# MAGIC And now with `N = 10,000`

# COMMAND ----------

calculate_js_distance(get_truncated_normal(upp=.80, n_size=10000), 
                      get_truncated_normal(upp=.79, n_size=10000)
                     )

# COMMAND ----------

# MAGIC %md 
# MAGIC And lastly, `N = 100,000`

# COMMAND ----------

calculate_js_distance(get_truncated_normal(upp=.80, n_size=100000), 
                      get_truncated_normal(upp=.79, n_size=100000)
                     )

# COMMAND ----------

# MAGIC %md
# MAGIC As illustrated above, the JS distance is much more resilient to increased sample size because it is smoothed and normalized. 

# COMMAND ----------

# MAGIC %md In practice, you would have data over a period of time, divide it into groups based on time (e.g. weekly windows), and then run the tests on the two groups to determine if there was a statistically significant change. The frequency of these monitoring jobs is depedent on the training window, inference data sample size, and use case. We'll simulate this with our dataset. 

# COMMAND ----------

# Load Dataset
airbnb_pdf = pd.read_parquet("/dbfs/mnt/training/airbnb/sf-listings/airbnb-cleaned-mlflow.parquet/")

# Identify Numeric & Categorical Columns
num_cols = ["accommodates", "bedrooms", "beds", "minimum_nights", "number_of_reviews", "review_scores_rating", "price"]
cat_cols = ["neighbourhood_cleansed", "property_type", "room_type"]

# Drop extraneous columns for this example
airbnb_pdf = airbnb_pdf[num_cols + cat_cols]

# Split Dataset into the two groups
pdf1 = airbnb_pdf.sample(frac = 0.5, random_state=1)
pdf2 = airbnb_pdf.drop(pdf1.index)

# COMMAND ----------

# MAGIC %md Alter `pdf2` to simulate drift. Add the following realistic changes: 
# MAGIC 
# MAGIC * ***The demand for Airbnbs skyrockted, so the prices of Airbnbs doubled***.
# MAGIC   * *Type of Drift*: Concept, Label 
# MAGIC * ***An upstream data management error resulted in null values for `neighbourhood_cleansed`***
# MAGIC   * *Type of Drift*: Feature
# MAGIC * ***An upstream data change resulted in `review_score_rating` move to a 5 star rating system, instead of the previous 100 point system. ***
# MAGIC   * *Type of Drift*: Feature

# COMMAND ----------

pdf2["price"] = 2 * pdf2["price"]
pdf2["review_scores_rating"] = pdf2["review_scores_rating"] / 20
pdf2["neighbourhood_cleansed"] = pdf2["neighbourhood_cleansed"].map(lambda x: None if x == 0 else x)

# COMMAND ----------

# MAGIC %md ## Apply Summary Stats
# MAGIC 
# MAGIC Start by looking at the summary statistics for the distribution of data in the two datasets. 

# COMMAND ----------

# Create visual of percent change in summary stats
cm = sns.light_palette("#2ecc71", as_cmap=True)
summary1_pdf = pdf1.describe()[num_cols]
summary2_pdf = pdf2.describe()[num_cols]
percent_change = 100 * abs((summary1_pdf - summary2_pdf) / (summary1_pdf + 1e-100))
percent_change.style.background_gradient(cmap=cm, text_color_threshold=0.5, axis=1)

# COMMAND ----------

# MAGIC %md The `review_scores_rating` and `price` seem to have many of their stats changed significantly, so we would want to look into those. Now run the KS test on the two subsets of the data. However, we cannot use the default alpha level of 0.05 in this situation because we are running a group of tests. This is because the probability of at least one false positive (concluding the feature's distribution changed when it did not) in a group of tests increases with the number of tests in the group. 
# MAGIC 
# MAGIC To solve this problem we will employ the **Bonferroni Correction**. This changes the alpha level to 0.05 / number of tests in group. It is common practice and reduces the probability of false positives. 
# MAGIC 
# MAGIC More information can be found [here](https://en.wikipedia.org/wiki/Bonferroni_correction).

# COMMAND ----------

# Set the Bonferroni Corrected alpha level
alpha = 0.05
alpha_corrected = alpha / len(num_cols)

# Loop over all numeric attributes (numeric cols and target col, price)
for num in num_cols:
    # Run test comparing old and new for that attribute
    ks_stat, ks_pval = stats.ks_2samp(pdf1[num], pdf2[num], mode="asymp")
    if ks_pval <= alpha_corrected:
        print(f"{num} had statistically significant change between the two samples")

# COMMAND ----------

# MAGIC %md Now, let's take a look at the categorical features. Check the rate of null values.

# COMMAND ----------

# Generate missing value counts visual 
pd.concat([100 * pdf1.isnull().sum() / len(pdf1), 100 * pdf2.isnull().sum() / len(pdf2)], axis=1, keys=["pdf1", "pdf2"]).style.background_gradient(cmap=cm, text_color_threshold=0.5, axis=1)

# COMMAND ----------

# MAGIC %md `neighbourhood_cleansed` has some missing values it did not before. Now, let's run the `Two-Way Chi Squared Contigency Test` for this example. This test works by creating a [Contingency Table](https://en.wikipedia.org/wiki/Contingency_table#:~:text=In%20statistics%2C%20a%20contingency%20table,frequency%20distribution%20of%20the%20variables.&text=They%20provide%20a%20basic%20picture,help%20find%20interactions%20between%20them.) with a column for the counts of each feature category for a given categorical feature and a row for `pdf1` and `pdf2`. 
# MAGIC 
# MAGIC It will then return a p-value determining whether or not there is an association between the time window of data and the distribution of that feature. If it is significant, we would conclude the distribution did change over time, and so there was drift. 

# COMMAND ----------

alpha = 0.05
corrected_alpha = alpha / len(cat_cols) # Still using the same correction
    
for feature in cat_cols:
    pdf_count1 = pd.DataFrame(pdf1[feature].value_counts()).sort_index().rename(columns={feature:"pdf1"})
    pdf_count2 = pd.DataFrame(pdf2[feature].value_counts()).sort_index().rename(columns={feature:"pdf2"})
    pdf_counts = pdf_count1.join(pdf_count2, how="outer").fillna(0)
    obs = np.array([pdf_counts["pdf1"], pdf_counts["pdf2"]])
    _, p, _, _ = stats.chi2_contingency(obs)
    if p < corrected_alpha:
        print(f"{feature} statistically significantly changed")
    else:
        print(f"{feature} did not statistically significantly change")

# COMMAND ----------

# MAGIC %md **Note:** The Two-way Chi-Squared test caught this not because nulls were introduced, but because they were introduced into one neighbourhood specifically, leading to an uneven distribution. If nulls were uniform throughout, then the test would see a similar distribution, just with lower counts, which this test would not flag as a change in dependence. 

# COMMAND ----------

# MAGIC %md Optional Note on Chi-Squared tests.
# MAGIC 
# MAGIC For the Chi-Squared tests, distributions with low bin counts can invalidate the test's accuracy and lead to false positives.  
# MAGIC 
# MAGIC There are also two types of Chi-Squared tests: One-way and Two-way (or contingency) tests. One-way testing is a goodness of fit test. It takes a single feature distribution and a population distribution and reports the probabilty of randomly drawing the single feature distribution from that population. In the context of drift monitoring, you would use the old time window as the population distribution and the new time window as the single feature distribution. If the p-value was low, then it would be likely that drift occured and that the new data no longer resembles the old distribution. This test compares counts, so if a more recent time window has a similar distribution but less data in it, this will return a low p-value when it perhaps should not. In that situation, try the Two-way test. 
# MAGIC 
# MAGIC The Two-way or contingency test used above is rather a test for independence. It takes in a table where the rows represent time window 1 and 2 and the columns represent feature counts for a given feature. It determines whether or not there is a relationship between the time window and the feature distributions, or, in other words, if the distributions are independent of the time window. It is important to note that this test will not catch differences such as a decrease in total counts in the distribution. This makes it useful when comparing time windows with unequal amounts of data, but make sure to check for changes in null counts or differences in counts separately that you might care about. 
# MAGIC 
# MAGIC Both of these assume high bin counts (generally >5) for each category in order to work properly. In our example, because of the large number of categories, some bin counts were lower than we would want for these tests. Fortunately, the scipy implementation of the Two-way test utilizes a correction for low counts that makes the Two-way preferable to the One-way in this situation, although ideally we would still want higher bin counts. 
# MAGIC 
# MAGIC The Fisher Exact test is a good alternative in the situation where the counts are too low, however there is currently no Python implemenation for this test in a contingency table larger than 2x2. If you are looking to run this test, you should explore using R. 
# MAGIC 
# MAGIC These are subtle differences that are worth taking into account, but in either case, a low p-value would indicate significantly different distributions across the time window and therefore drift for the One-Way or Two-way Chi-Squared. 

# COMMAND ----------

# MAGIC %md ## Combine into One Class
# MAGIC 
# MAGIC Here, we'll combine the tests and code we have seen so far into a class `Monitor` that shows how you might implement the code above in practice. 

# COMMAND ----------

import pandas as pd
import seaborn as sns
from scipy import stats
import numpy as np 

class Monitor():
  
    def __init__(self, pdf1, pdf2, cat_cols, num_cols, alpha=.05):
        """
        Pass in two pandas dataframes with the same columns for two time windows
        List the categorical and numeric columns, and optionally provide an alpha level
        """
        assert (pdf1.columns == pdf2.columns).all(), "Columns do not match"
        self.pdf1 = pdf1
        self.pdf2 = pdf2
        self.alpha = alpha
        self.categorical_columns = cat_cols
        self.continuous_columns = num_cols
    
    def run(self):
        """
        Call to run drift monitoring
        """
        self.handle_numeric()
        self.handle_categorical()
  
    def handle_numeric(self):
        """
        Handle the numeric features with the Two-Sample Kolmogorov-Smirnov (KS) Test with Bonferroni Correction 
        """
        corrected_alpha = self.alpha / len(self.continuous_columns)

        for num in self.continuous_columns:
            ks_stat, ks_pval = stats.ks_2samp(self.pdf1[num], self.pdf2[num], mode="asymp")
            if ks_pval <= corrected_alpha:
                self.on_drift(num)
      
    def handle_categorical(self):
        """
        Handle the Categorical features with Two-Way Chi-Squared Test with Bonferroni Correction
        """
        corrected_alpha = self.alpha / len(self.categorical_columns)

        for feature in self.categorical_columns:
            pdf_count1 = pd.DataFrame(self.pdf1[feature].value_counts()).sort_index().rename(columns={feature:"pdf1"})
            pdf_count2 = pd.DataFrame(self.pdf2[feature].value_counts()).sort_index().rename(columns={feature:"pdf2"})
            pdf_counts = pdf_count1.join(pdf_count2, how="outer").fillna(0)
            obs = np.array([pdf_counts["pdf1"], pdf_counts["pdf2"]])
            _, p, _, _ = stats.chi2_contingency(obs)
            if p < corrected_alpha:
                self.on_drift(feature)

    def generate_null_counts(self, palette="#2ecc71"):
        """
        Generate the visualization of percent null counts of all features
        Optionally provide a color palette for the visual
        """
        cm = sns.light_palette(palette, as_cmap=True)
        return pd.concat([100 * self.pdf1.isnull().sum() / len(self.pdf1), 
                          100 * self.pdf2.isnull().sum() / len(self.pdf2)], axis=1, 
                          keys=["pdf1", "pdf2"]).style.background_gradient(cmap=cm, text_color_threshold=0.5, axis=1)
    
    def generate_percent_change(self, palette="#2ecc71"):
        """
        Generate visualization of percent change in summary statistics of numeric features
        Optionally provide a color palette for the visual
        """
        cm = sns.light_palette(palette, as_cmap=True)
        summary1_pdf = self.pdf1.describe()[self.continuous_columns]
        summary2_pdf = self.pdf2.describe()[self.continuous_columns]
        percent_change = 100 * abs((summary1_pdf - summary2_pdf) / (summary1_pdf + 1e-100))
        return percent_change.style.background_gradient(cmap=cm, text_color_threshold=0.5, axis=1)
  
    def on_drift(self, feature):
        """
        Complete this method with your response to drift.  Options include:
          - raise an alert
          - automatically retrain model
        """
        print(f"Drift found in {feature}!")
    
drift_monitor = Monitor(pdf1, pdf2, cat_cols, num_cols)
drift_monitor.run()

# COMMAND ----------

drift_monitor.generate_percent_change()

# COMMAND ----------

drift_monitor.generate_null_counts()

# COMMAND ----------

# MAGIC %md ## Drift Monitoring Architecture
# MAGIC 
# MAGIC A potential workflow for deployment and dirft monitoring could look something like this:
# MAGIC 
# MAGIC ![Azure ML Pipeline](https://files.training.databricks.com/images/monitoring.png)
# MAGIC 
# MAGIC **Workflow**
# MAGIC * ***Deploy a model to production, using MLflow and Delta to log the model and data***
# MAGIC * ***When the next time step of data arrives:***
# MAGIC   * Get the logged input data from the current production model
# MAGIC   * Get the observed (true) values
# MAGIC   * Compare the evaluation metric (e.g. RMSE) between the observed values and predicted values
# MAGIC   * Run the statistical tests shown above to identify potential drift
# MAGIC * ***If drift is not found:***
# MAGIC   * Keep monitoring but leave original model deployed
# MAGIC * ***If drift is found:***
# MAGIC   * Analyze the situation and take action
# MAGIC   * If retraining/deploying an updated model is needed:
# MAGIC     * Create a candidate model on the new data
# MAGIC     * Deploy candidate model as long as it performs better than the current model on the more recent data

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## Other Drift Monitoring Methods
# MAGIC 
# MAGIC In this lesson, we focused on statistical methods for identifying drift. 
# MAGIC 
# MAGIC However, there are other methods.
# MAGIC 
# MAGIC [The package `skmultiflow`](https://scikit-multiflow.github.io/) has some good options for drift detection algorithms. Try the DDM method.
# MAGIC 
# MAGIC 
# MAGIC <div><img src="https://files.training.databricks.com/images/eLearning/ML-Part-4/drift.png" style="height: 400px; margin: 20px"/></div>
# MAGIC 
# MAGIC The detection threshold is calculated as a function of two statistics, obtained when `(pi + si)` is minimum:
# MAGIC 
# MAGIC  * `pmin`: The minimum recorded error rate
# MAGIC  * `smin`: The minimum recorded standard deviation
# MAGIC 
# MAGIC At instant `i`, the detection algorithm uses:
# MAGIC 
# MAGIC  * `pi`: The error rate at instant i
# MAGIC  * `si`: The standard deviation at instant i
# MAGIC 
# MAGIC The default conditions for entering the warning zone and detecting change are as follows:
# MAGIC 
# MAGIC  * if `pi + si >= pmin + 2 * smin` -> Warning zone
# MAGIC  * if `pi + si >= pmin + 3 * smin` -> Change detected
# MAGIC 
# MAGIC #### Model Based Approaches
# MAGIC 
# MAGIC A much less intuitive but possibly more powerful approach would focus on a machine learning based solution. 
# MAGIC 
# MAGIC Some common examples: 
# MAGIC 
# MAGIC 1. Create a supervised approach on a dataset of data classified as normal or abnormal. Finding such a dataset can be difficult, however. 
# MAGIC 2. Use a regression method to predict future values for incoming data over time and detect drift if there is strong prediction error. 

# COMMAND ----------

# MAGIC %md #### Other Resources
# MAGIC 
# MAGIC For more information, a great talk by Chengyin Eng and Niall Turbitt can be found here: [Drifting Away: Testing ML Models in Production](https://databricks.com/session_na21/drifting-away-testing-ml-models-in-production).
# MAGIC 
# MAGIC Much of the content in this lesson is adapted from this talk. 

# COMMAND ----------

# MAGIC %md
# MAGIC ## ![Spark Logo Tiny](https://files.training.databricks.com/images/105/logo_spark_tiny.png) Next Steps
# MAGIC 
# MAGIC Start the labs for this lesson, [Monitoring Lab]($./Labs/01-Monitoring-Lab)

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC &copy; 2021 Databricks, Inc. All rights reserved.<br/>
# MAGIC Apache, Apache Spark, Spark and the Spark logo are trademarks of the <a href="http://www.apache.org/">Apache Software Foundation</a>.<br/>
# MAGIC <br/>
# MAGIC <a href="https://databricks.com/privacy-policy">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use">Terms of Use</a> | <a href="http://help.databricks.com/">Support</a>
