Elasticsearch connector for Search UI is currently in technical preview status. It is not ready for production use.  
适用于搜索 UI 的 Elasticsearch 连接器目前处于技术预览状态。它尚未准备好用于生产。

This tutorial will guide you through the process of creating a Search UI with Elasticsearch directly, using the `elasticsearch-connector`. We will be using a sample movie data-set of around 1000 movies.  
本教程将指导您直接使用 Elasticsearch 创建搜索 UI 的过程，使用 `elasticsearch-connector` .我们将使用大约 1000 部电影的示例电影数据集。

Within this tutorial, we assume that you have Node.js installed on your machine.  
在本教程中，我们假设您的计算机上安装了 Node.js。

## [](https://docs.elastic.co/search-ui/tutorials/elasticsearch#step-1-setup-elasticsearch)Step 1: Setup Elasticsearch  
第 1 步：设置 Elasticsearch

First we need to setup Elasticsearch. The easiest way to do this is to create an Elasticsearch instance via [Elastic Cloud](https://cloud.elastic.co/registration).  
首先，我们需要设置 Elasticsearch。最简单的方法是通过 Elastic Cloud 创建一个 Elasticsearch 实例。

### [](https://docs.elastic.co/search-ui/tutorials/elasticsearch#setting-up-an-index)Setting up an Index  
设置索引

We are going to issue commands via [Kibana's dev tools console](https://www.elastic.co/guide/en/kibana/current/console-kibana.html). You can alternatively use a REST client like Postman to achieve this.  
我们将通过 Kibana 的开发工具控制台发出命令。您也可以使用像 Postman 这样的 REST 客户端来实现这一点。

First we need to create an index for our data. We can do this simply via the following request:  
首先，我们需要为数据创建一个索引。我们可以通过以下请求简单地做到这一点：

Elasticsearch will acknowledge our request in the response.  
Elasticsearch将在回复中确认我们的请求。

### [](https://docs.elastic.co/search-ui/tutorials/elasticsearch#setting-up-a-read-only-api-key)Setting up a read-only API Key  
设置只读 API 密钥

Next we need to setup an API key to access the data from the index. We can do this via Kibana's Stack Management API Keys page (`<your Kibana endpoint>/app/management/security/api_keys`). Note that security needs to be enabled for this option to be available.  
接下来，我们需要设置一个 API 密钥来访问索引中的数据。我们可以通过 Kibana 的堆栈管理 API 密钥页面 （ ） 执行此操作 `<your Kibana endpoint>/app/management/security/api_keys` 。请注意，需要启用安全性才能使用此选项。

Notice here we are only giving read privileges for this api key. You will need to setup an api key with write privileges to add and update data to the index.  
请注意，这里我们只授予此 api 密钥的读取权限。您需要设置具有写入权限的 api 密钥，以向索引添加和更新数据。

```
{
  "superuser": {
    "cluster": ["all"],
    "indices": [
      {
        "names": ["my-example-movies"],
        "privileges": ["read"],
        "allow_restricted_indices": false
      }
    ]
  }
}
```

Once saved, you are presented with the api-key. Copy this and keep it safe. We will need to use this further down in the tutorial.  
保存后，您将看到 API 密钥。复制此内容并保证其安全。我们需要在本教程中进一步使用它。

### [](https://docs.elastic.co/search-ui/tutorials/elasticsearch#enabling-cors)Enabling CORS 启用 CORS

If you're going to be accessing Elasticsearch directly from a browser and the Elasticsearch host domain doesn't match your site's domain, you will need to enable CORS.  
如果您要直接从浏览器访问 Elasticsearch，并且 Elasticsearch 主机域与您站点的域不匹配，则需要启用 CORS。

CORS is a browser mechanism which enables controlled access to resources located outside of the current domain. In order for the browser to make requests to Elasticsearch, CORS configuration headers need to specified in the Elasticsearch configuration.  
CORS 是一种浏览器机制，可实现对当前域外部资源的受控访问。为了让浏览器向 Elasticsearch 发出请求，需要在 Elasticsearch 配置中指定 CORS 配置标头。

You can do this in cloud by going to the deployment settings for your Elasticsearch instance, click "Edit user settings and plugins" and under "user settings", add the CORS configuration below:  
您可以在云中执行此操作，方法是转到 Elasticsearch 实例的部署设置，单击“编辑用户设置和插件”，然后在“用户设置”下添加以下 CORS 配置：

```
http.cors.allow-origin: "*"
http.cors.enabled: true
http.cors.allow-credentials: true
http.cors.allow-methods: OPTIONS, HEAD, GET, POST, PUT, DELETE
http.cors.allow-headers: X-Requested-With, X-Auth-Token, Content-Type, Content-Length, Authorization, Access-Control-Allow-Headers, Accept, x-elastic-client-meta
```

then save. Your Elasticsearch instance will be restarted and the CORS configuration will be active.  
然后保存。您的 Elasticsearch 实例将重新启动，CORS 配置将处于活动状态。

## [](https://docs.elastic.co/search-ui/tutorials/elasticsearch#step-2-setup-movies-index)Step 2: Setup Movies Index  
第 2 步：设置电影索引

Next we need to setup the index fields, ready for us to ingest data.  
接下来，我们需要设置索引字段，为我们摄取数据做好准备。

The mapping for an index depends on the data you want to index and the features you want.  
索引的映射取决于要编制索引的数据和所需的要素。

### [](https://docs.elastic.co/search-ui/tutorials/elasticsearch#examples)Examples 例子

We want to be able to search on title. We need only one field of type text.  
我们希望能够搜索标题。我们只需要一个文本类型的字段。

```
{
  "properties": {
    "title": {
      "type": "text"
    }
  }
}
```

We want to be able to search and product facets for writers field. We need two fields of different types: keyword and text.  
我们希望能够搜索和产品方面为作家领域。我们需要两个不同类型的字段：关键字和文本。

```
{
  "properties": {
    "writers": {
      "type": "text",
      "fields": {
        "keyword": {
          "type": "keyword"
        }
      }
    }
  }
}
```

We want to be able to filter on a date field. We only need one date field.  
我们希望能够对日期字段进行筛选。我们只需要一个日期字段。

```
{
  "properties": {
    "released": {
      "type": "date"
    }
  }
}
```

We want to be able to filter on a numeric field. We only need one numeric field. Can be a choice of integer, float and [more documented here](https://www.elastic.co/guide/en/elasticsearch/reference/current/number.html)  
我们希望能够对数值字段进行过滤。我们只需要一个数值字段。可以选择整数、浮点数和更多记录在这里

```
{
  "properties": {
    "imdbRating": {
      "type": "float"
    }
  }
}
```

For our movie data-set, we will be using the following fields:  
对于我们的电影数据集，我们将使用以下字段：

-   title (searchable) 标题（可搜索）
-   plot (searchable) 绘图（可搜索）
-   genre (searchable, facetable)  
    流派（可搜索、可分面）
-   actors (searchable, facetable)  
    演员（可搜索、可查看）
-   directors (searchable, facetable)  
    导演（可搜索、可查看）
-   released (filterable) 已发布（可过滤）
-   imdbRating (filterable) imdb评级（可过滤）
-   url

The mapping file will be as follows, and we'll once again use Kibana's dev tools console to update the mapping file for our index.  
映射文件如下所示，我们将再次使用 Kibana 的开发工具控制台来更新索引的映射文件。

```
PUT /my-example-movies/_mapping
{
  "properties": {
    "title": {
      "type": "text",
      "fields": {
        "suggest": {
          "type": "search_as_you_type"
        }
      }
    },
    "plot": {
      "type": "text"
    },
    "genre": {
      "type": "text",
      "fields": {
        "keyword": {
          "type": "keyword"
        }
      }
    },
    "actors": {
      "type": "text",
      "fields": {
        "keyword": {
          "type": "keyword"
        }
      }
    },
    "directors": {
      "type": "text",
      "fields": {
        "keyword": {
          "type": "keyword"
        }
      }
    },
    "released": {
      "type": "date"
    },
    "imdbRating": {
      "type": "float"
    },
    "url": {
      "type": "keyword"
    },
    "movie_completion": {
      "type": "completion"
    }
  }
}
```

Elasticsearch will acknowledge the request in the response.  
Elasticsearch 将在响应中确认请求。

We also want to provide autocomplete functionality, so we need to setup fields for autocomplete.  
我们还希望提供自动完成功能，因此我们需要设置自动完成字段。

For suggestions, we want to suggest terms that appear within the actors, directors and genre fields. For quick result hits, we want to suggest movies that partially match the title field.  
对于建议，我们希望建议出现在演员、导演和类型字段中的术语。为了快速获得结果，我们希望推荐与标题字段部分匹配的电影。

In the above example:  
在上面的例子中：

-   we have included `movie_completion` field, which is used to provide suggestion completion functionality. This field is not searchable, but is used to provide autocomplete functionality.  
    我们包含了 `movie_completion` 字段，用于提供建议完成功能。此字段不可搜索，但用于提供自动完成功能。
-   we have included a `suggest` field for the title field. This field is searchable, but is used to provide "quick hits" functionality.  
    我们为标题字段包含一个 `suggest` 字段。此字段是可搜索的，但用于提供“快速命中”功能。

## [](https://docs.elastic.co/search-ui/tutorials/elasticsearch#step-3-index-movies-data)Step 3: Index Movies Data  
步骤 3：索引电影数据

Now with our index and mapping file created, we are ready to index some data! We will use the bulk API to index our data.  
现在，随着我们的索引和映射文件的创建，我们已经准备好索引一些数据了！我们将使用批量 API 来索引我们的数据。

We will use the following request. In this example we will be indexing the first movie in the data-set to verify that the data fields is being indexed correctly.  
我们将使用以下请求。在此示例中，我们将为数据集中的第一部电影编制索引，以验证数据字段是否正确编制索引。

```
PUT /my-example-movies/_bulk
{ "index": {}}
{"title": "The Godfather", "released": "1972-03-23T23:00:00.000Z","genre": ["Crime", "Drama"],"directors": ["Francis Ford Coppola"],"actors": ["Marlon Brando", "Al Pacino", "James Caan", "Richard S. Castellano"],"plot": "The aging patriarch of an organized crime dynasty transfers control of his clandestine empire to his reluctant son.","imdbRating": "9.2", "movie_completion": ["Crime", "Drama", "Marlon Brando", "Al Pacino", "James Caan", "Richard S. Castellano"], "url": "https://www.imdb.com/title/tt0068646/"}
```

## [](https://docs.elastic.co/search-ui/tutorials/elasticsearch#step-4-setup-cra-for-search-ui)Step 4: Setup CRA for Search UI  
步骤 4：为搜索 UI 设置 CRA

First, download the Search-UI's starter app from github by  
首先，通过以下方式从github下载Search-UI的入门应用程序

```
curl https://codeload.github.com/elastic/app-search-reference-ui-react/tar.gz/master | tar -xz
```

and should appear as a folder called `app-search-reference-ui-react-main`.  
并且应显示为名为 `app-search-reference-ui-react-main` 的文件夹。

Navigate to the root to the folder and install the dependencies using the following command:  
导航到文件夹的根目录，并使用以下命令安装依赖项：

### [](https://docs.elastic.co/search-ui/tutorials/elasticsearch#installing-connector)Installing connector 安装连接器

Within the folder, we can now install the `@elastic/search-ui-elasticsearch-connector` library with Yarn.  
在该文件夹中，我们现在可以使用 Yarn 安装 `@elastic/search-ui-elasticsearch-connector` 库。

```
yarn add @elastic/search-ui-elasticsearch-connector
```

Make sure to check and update Search UI dependencies to the latest version. You can find the latest version by going to [NPM's page for @elastic/search-ui](https://www.npmjs.com/package/@elastic/search-ui).  
请确保检查搜索 UI 依赖项并将其更新到最新版本。您可以通过访问 NPM 的页面获取 @elastic/search-ui 来找到最新版本。

### [](https://docs.elastic.co/search-ui/tutorials/elasticsearch#setting-up-the-connector)Setting up the connector  
设置连接器

Open the project within your favorite editor.  
在您喜欢的编辑器中打开项目。

Within `src/App.js`, change line 3 to import the Elasticsearch connector. You no longer need the app-search connector.  
在 中 `src/App.js` ，更改第 3 行以导入 Elasticsearch 连接器。不再需要应用搜索连接器。

```
import ElasticsearchAPIConnector from "@elastic/search-ui-elasticsearch-connector";
```

and then update the options to the connector  
，然后将选项更新到连接器

```
const connector = new ElasticsearchAPIConnector({
  cloud: {
    id: "<my-elastic-cloud-id>"
  },
  apiKey: "<api-key>",
  index: "my-example-movies"
});
```

If you're using Elastic Cloud, you can find your cloud id within your deployment's details.  
如果您使用的是 Elastic Cloud，则可以在部署的详细信息中找到您的云 ID。

alternatively, if you're using an on-premise Elasticsearch instance, you can connect via specifying the host.  
或者，如果您使用的是本地 Elasticsearch 实例，则可以通过指定主机进行连接。

```
const connector = new ElasticsearchAPIConnector({
  host: "http://localhost:9200",
  index: "my-example-movies"
});
```

## [](https://docs.elastic.co/search-ui/tutorials/elasticsearch#step-5-configure-search-ui)Step 5: Configure Search UI  
步骤 5：配置搜索 UI

Next lets configure Search UI for our needs! Navigate to the config within app.js and update the following:  
接下来，让我们根据自己的需求配置搜索 UI！导航到应用程序中的配置.js并更新以下内容：

```
const config = {
  searchQuery: {
    search_fields: {
      title: {
        weight: 3
      },
      plot: {},
      genre: {},
      actors: {},
      directors: {}
    },
    result_fields: {
      title: {
        snippet: {}
      },
      plot: {
        snippet: {}
      }
    },
    disjunctiveFacets: ["genre.keyword", "actors.keyword", "directors.keyword"],
    facets: {
      "genre.keyword": { type: "value" },
      "actors.keyword": { type: "value" },
      "directors.keyword": { type: "value" },
      released: {
        type: "range",
        ranges: [
          {
            from: "2012-04-07T14:40:04.821Z",
            name: "Within the last 10 years"
          },
          {
            from: "1962-04-07T14:40:04.821Z",
            to: "2012-04-07T14:40:04.821Z",
            name: "10 - 50 years ago"
          },
          {
            to: "1962-04-07T14:40:04.821Z",
            name: "More than 50 years ago"
          }
        ]
      },
      imdbRating: {
        type: "range",
        ranges: [
          { from: 1, to: 3, name: "Pants" },
          { from: 3, to: 6, name: "Mediocre" },
          { from: 6, to: 8, name: "Pretty Good" },
          { from: 8, to: 10, name: "Excellent" }
        ]
      }
    }
  },
  autocompleteQuery: {
    results: {
      resultsPerPage: 5,
      search_fields: {
        "title.suggest": {
          weight: 3
        }
      },
      result_fields: {
        title: {
          snippet: {
            size: 100,
            fallback: true
          }
        },
        url: {
          raw: {}
        }
      }
    },
    suggestions: {
      types: {
        results: { fields: ["movie_completion"] }
      },
      size: 4
    }
  },
  apiConnector: connector,
  alwaysSearchOnInitialLoad: true
};
```

In the above example, we configured the:  
在上面的示例中，我们配置了：

-   query fields to search on title, plot, genre, actors and directors using the text fields  
    查询字段以使用文本字段搜索标题、情节、流派、演员和导演
-   result fields to display title, plot, genre, actors and directors using the text fields  
    结果字段，用于使用文本字段显示标题、情节、流派、演员和导演
-   facets to display genre, actors and directors using the keyword fields  
    使用关键字字段显示类型、演员和导演的方面
-   we made the facets disjunctive for better user experience. The user can select more than one facet to expand their search.  
    我们使分面分离，以获得更好的用户体验。用户可以选择多个方面来扩展其搜索。
-   autocomplete results to suggest results with the same query fields as main search + returning some fields for display.  
    自动完成结果以建议具有与主搜索相同的查询字段的结果 + 返回一些字段以供显示。

For more information on configuration, visit the [API configuration docs](https://docs.elastic.co/search-ui/api/core/configuration).  
有关配置的更多信息，请访问 API 配置文档。

### [](https://docs.elastic.co/search-ui/tutorials/elasticsearch#updating-components)Updating Components 更新组件

We are going to do several steps here:  
我们将在这里执行几个步骤：

-   update the `<Searchbox />` component to configure autocomplete  
    更新 `<Searchbox />` 组件以配置自动完成
-   remove sorting options 删除排序选项
-   add a `<Facet />` component for each facet field  
    为每个分面字段添加一个 `<Facet />` 组件
-   update the `<Results />` component to display all the fields  
    更新 `<Results />` 组件以显示所有字段

```
<div className="App">
  <ErrorBoundary>
    <Layout
      header={
        <SearchBox
          autocompleteMinimumCharacters={3}
          autocompleteResults={{
            linkTarget: "_blank",
            sectionTitle: "Results",
            titleField: "title",
            urlField: "url",
            shouldTrackClickThrough: true
          }}
          autocompleteSuggestions={true}
          debounceLength={0}
        />
      }
      sideContent={
        <div>
          {wasSearched && <Sorting label={"Sort by"} sortOptions={[]} />}
          <Facet key={"1"} field={"genre.keyword"} label={"genre"} />
          <Facet key={"2"} field={"actors.keyword"} label={"actors"} />
          <Facet key={"3"} field={"directors.keyword"} label={"directors"} />
          <Facet key={"4"} field={"released"} label={"released"} />
          <Facet key={"4"} field={"imdbRating"} label={"imdb rating"} />
        </div>
      }
      bodyContent={<Results shouldTrackClickThrough={true} />}
      bodyHeader={
        <React.Fragment>
          {wasSearched && <PagingInfo />}
          {wasSearched && <ResultsPerPage />}
        </React.Fragment>
      }
      bodyFooter={<Paging />}
    />
  </ErrorBoundary>
</div>
```

## [](https://docs.elastic.co/search-ui/tutorials/elasticsearch#step-6-test-drive)Step 6: Test Drive!

Lets run the project with the command:

and then view the results in the browser at [http://localhost:3000/](http://localhost:3000/)

## [](https://docs.elastic.co/search-ui/tutorials/elasticsearch#next-steps)Next Steps

Lets recap of the steps we have covered:

-   we setup and configured the Elasticsearch index for our data
-   we indexed an example movie
-   we checked out the starter app and added the Elasticsearch connector
-   we configured the Elasticsearch connector to connect to our Elasticsearch index
-   we updated the Search UI configuration to specify the fields to be searchable, facetable
-   we updated the components to use these fields

Next you can add more data into the index, [update the results view to display more fields](https://docs.elastic.co/search-ui/api/react/components/result#view-customization), and deploy the app.