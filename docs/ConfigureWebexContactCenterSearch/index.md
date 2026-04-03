# Webex Contact Center - Search

The **Webex Contact Center - Search** input is used to fetch the data from [Webex Contact Center - Search](https://developer.webex.com/webex-contact-center/docs/api/v1/search/search) endpoint. It allows users to retrieve Agent Activity Record, Agent Session Record, Customer Activity Record, Customer Session Record.

**Prerequisites**: This input is only available to Webex Contact Cetner Administrator or Supervisor.

The `Start Time` is required. The Start time is inclusive and should be in the format YYYY-MM-DDTHH:MM:SSZ (example:2023-01-01T00:00:00Z). It cannot be older than 36 months from the current time. The first ingestion may pull a lot of data, please make sure you set a large interval when your Start Time is older than 1 month from current time.

The `End Time` is optional. If you set it to be a specific date, only logs within the time range from Start Date to End Date will be ingested. The format should be YYYY-MM-DDTHH:MM:SSZ (example:2023-02-01T00:00:00Z). The duration between Start Time and End Time must not be more than 365 days. Leave it blank if an ongoing ingestion mode is needed.

The `Query Template` is required. Please select the data source you wish to ingest into Splunk from the four options below. If you require all of them, please create four separate inputs.

- Agent Activity Record(AAR): Represents an atomic step in the agent workflow.
- Agent Session Record(ASR): Represents the agent workflow, consisting of a sequence of agent activities.
- Customer Activity Record(CAR): Represents an atomic step in the customer workflow.
- Customer Session Record(CSR): Represents the customer workflow, consisting of a sequence of customer activities.

For more information on each data source, please check [here](https://help.webex.com/en-us/article/tajemk/Cisco-Webex-Contact-Center-Analyzer-User-Guide#reference-template_2df0d0a4-4fac-4758-82a7-1fa59961b472).

The input uses checkpointing to avoid ingesting duplicate data. After the initial run, the script will save the end time of the last round as the checkpoint, and will be used as the `Start Time` (advancing by one millisecond) for the next run.

## Configure Webex Security Audit Events input through Splunk Web 

1. In the **Inputs** tab select **Create New Input**.
2. Choose **Webex Contact Center - Search**.
3. Enter the information in the related fields using the following input parameters table.

## Input Parameters 

Each attribute in the following table corresponds to a field in Splunk Web.

|Input name               |Corresponding field in Splunk Web | Description|
|-------------------------|----------------------------------|------------|
|`name`                   |Name                              |A unique name for your input.|
|`interval`               |Interval                          |Time interval of input in seconds.|
|`index`                  |Index                             |The index in which the data should be stored. The default is <code>default</code>.|
|`account`                |Global Account                    |The Webex account created in the Configuration tab.|
|`org_id`             |Org ID                        |Required, Enter your Webex Contact Center Orgnization ID.|
|`start_time`             |Start Time                        |Required, Start date and time (inclusive) in the format YYYY-MM-DDTHH:MM:SSZ, `example:2023-01-01T00:00:00Z`.|
|`end_time`               |End Time                          |Optional, End date and time in the format YYYY-MM-DDTHH:MM:SSZ, `example:2023-02-01T00:00:00Z`. Leave it blank if an ongoing ingestion mode is needed.|
|`query_template`               |Query Template                         |Required, ESelect the appropriate Query Template for the data source you wish to ingest.|